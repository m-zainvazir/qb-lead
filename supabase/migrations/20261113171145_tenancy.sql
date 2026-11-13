-- Module 1: tenants, memberships, platform admins, invitations, audit log.
--
-- Rules (CLAUDE.md, docs/decisions/0001-db-access.md):
--   * every table: RLS enabled AND forced; anon gets nothing
--   * every grant is explicit; Supabase's default grants on public tables are revoked
--   * helpers live in schema `private`, which the Data API does not expose
--   * all times are timestamptz (UTC)

create extension if not exists citext with schema extensions;

-- ---------------------------------------------------------------------------
-- 0. Safer defaults for every future table in public.
--    Supabase's defaults hand anon/authenticated TRUNCATE, REFERENCES, TRIGGER and
--    MAINTAIN on new tables. New tables must grant exactly what they need.
-- ---------------------------------------------------------------------------
alter default privileges for role postgres in schema public
  revoke all on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke all on sequences from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke all on functions from public, anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- 1. Private schema for helpers
-- ---------------------------------------------------------------------------
create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated, service_role;
alter default privileges for role postgres in schema private
  revoke all on functions from public;

create function private.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end
$$;

-- ---------------------------------------------------------------------------
-- 2. Tables
-- ---------------------------------------------------------------------------
create table public.tenants (
  id            uuid primary key default gen_random_uuid(),
  name          text not null check (char_length(btrim(name)) between 1 and 120),
  type          text not null check (type in ('freelancer', 'agency')),
  status        text not null default 'active' check (status in ('active', 'suspended', 'deleted')),
  is_internal   boolean not null default false,
  branding      jsonb not null default '{}'::jsonb check (jsonb_typeof(branding) = 'object'),
  custom_domain extensions.citext unique,
  created_by    uuid references auth.users (id) on delete set null,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
comment on table public.tenants is 'A customer company. Suspend or soft-delete first; hard deletion is a separate job.';

create table public.memberships (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id) on delete restrict,
  user_id    uuid not null references auth.users (id) on delete cascade,
  role       text not null check (role in ('owner', 'admin', 'member')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, user_id)
);
create index memberships_user_id_idx on public.memberships (user_id);

create table public.platform_admins (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  level      text not null check (level in ('super', 'support')),
  created_at timestamptz not null default now(),
  created_by text not null default current_user
);
comment on table public.platform_admins is 'Created by SQL only (supabase/snippets/create_platform_admin.sql), never through a screen.';

create table public.invitations (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id) on delete restrict,
  email       extensions.citext not null
              check (char_length(email) <= 320 and email operator(pg_catalog.~) '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  role        text not null check (role in ('admin', 'member')),
  token_hash  text not null unique check (token_hash ~ '^[0-9a-f]{64}$'),
  invited_by  uuid not null default auth.uid() references auth.users (id) on delete cascade,
  expires_at  timestamptz not null default (now() + interval '7 days'),
  accepted_at timestamptz,
  accepted_by uuid references auth.users (id) on delete set null,
  revoked_at  timestamptz,
  created_at  timestamptz not null default now(),
  check (expires_at <= created_at + interval '7 days')
);
create index invitations_tenant_id_idx on public.invitations (tenant_id, created_at desc);
create unique index invitations_one_open_per_email
  on public.invitations (tenant_id, email) where accepted_at is null and revoked_at is null;

create table public.audit_log (
  id            bigint generated always as identity primary key,
  occurred_at   timestamptz not null default now(),
  actor_user_id uuid,          -- no FK: history outlives the user
  actor_kind    text not null check (actor_kind in ('user', 'platform_admin', 'system')),
  tenant_id     uuid,          -- no FK: history outlives the tenant
  action        text not null check (action ~ '^[a-z_]+(\.[a-z_]+)+$'),
  target_type   text,
  target_id     text,
  metadata      jsonb not null default '{}'::jsonb,
  request_id    text,
  ip            inet
);
create index audit_log_tenant_id_idx on public.audit_log (tenant_id, occurred_at desc);
create index audit_log_actor_idx on public.audit_log (actor_user_id, occurred_at desc);

create trigger tenants_touch before update on public.tenants
  for each row execute function private.touch_updated_at();
create trigger memberships_touch before update on public.memberships
  for each row execute function private.touch_updated_at();

-- ---------------------------------------------------------------------------
-- 3. Helper functions used by policies (SECURITY DEFINER avoids recursion on memberships)
-- ---------------------------------------------------------------------------
create function private.is_member(p_tenant_id uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1
    from public.memberships m
    join public.tenants t on t.id = m.tenant_id
    where m.tenant_id = p_tenant_id
      and m.user_id = (select auth.uid())
      and t.status = 'active'
  );
$$;

create function private.has_role(p_tenant_id uuid, p_roles text[]) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1
    from public.memberships m
    join public.tenants t on t.id = m.tenant_id
    where m.tenant_id = p_tenant_id
      and m.user_id = (select auth.uid())
      and m.role = any (p_roles)
      and t.status = 'active'
  );
$$;

-- Platform admin AND signed in with MFA (aal2).
create function private.is_platform_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select auth.jwt() ->> 'aal'), '') = 'aal2'
     and exists (select 1 from public.platform_admins pa where pa.user_id = (select auth.uid()));
$$;

-- The JWT's session still exists (sign-out everywhere and password reset end it).
create function private.session_is_active() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from auth.sessions s
    where s.id = nullif((select auth.jwt() ->> 'session_id'), '')::uuid
      and s.user_id = (select auth.uid())
      and (s.not_after is null or s.not_after > now())
  );
$$;

-- ---------------------------------------------------------------------------
-- 4. Audit log: append-only for everyone, including the table owner
-- ---------------------------------------------------------------------------
create function private.audit_log_is_append_only() returns trigger
language plpgsql set search_path = '' as $$
begin
  raise exception 'audit_log is append-only' using errcode = '42501';
end
$$;
create trigger audit_log_no_update_delete before update or delete on public.audit_log
  for each row execute function private.audit_log_is_append_only();
create trigger audit_log_no_truncate before truncate on public.audit_log
  for each statement execute function private.audit_log_is_append_only();

-- Written from user_db(): the actor is always auth.uid(); request id and IP come from
-- transaction settings the API sets (app.request_id, app.client_ip).
create function private.write_audit(
  p_action text,
  p_tenant_id uuid,
  p_target_type text default null,
  p_target_id text default null,
  p_metadata jsonb default '{}'::jsonb
) returns void
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_uid uuid := (select auth.uid());
begin
  if v_uid is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;
  if p_tenant_id is not null and not private.is_member(p_tenant_id) then
    raise exception 'not a member of this tenant' using errcode = '42501';
  end if;
  insert into public.audit_log (actor_user_id, actor_kind, tenant_id, action, target_type,
                                target_id, metadata, request_id, ip)
  values (v_uid, 'user', p_tenant_id, p_action, p_target_type, p_target_id,
          coalesce(p_metadata, '{}'::jsonb),
          nullif(current_setting('app.request_id', true), ''),
          nullif(current_setting('app.client_ip', true), '')::inet);
end
$$;

-- ---------------------------------------------------------------------------
-- 5. Memberships: every active tenant keeps at least one owner
-- ---------------------------------------------------------------------------
create function private.keep_one_owner() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.role = 'owner'
     and (tg_op = 'DELETE' or new.role <> 'owner')
     and exists (select 1 from public.tenants t where t.id = old.tenant_id and t.status <> 'deleted')
     and not exists (
       select 1 from public.memberships m
       where m.tenant_id = old.tenant_id and m.role = 'owner' and m.id <> old.id
     )
  then
    raise exception 'a company must keep at least one owner' using errcode = 'LG409';
  end if;
  return coalesce(new, old);
end
$$;
create trigger memberships_keep_one_owner before update or delete on public.memberships
  for each row execute function private.keep_one_owner();

-- ---------------------------------------------------------------------------
-- 6. Operations that need more than one table (called from user_db as `authenticated`)
--    Errors: LG400 bad input, LG403 not allowed, LG404 not found/invalid, LG409 conflict.
-- ---------------------------------------------------------------------------
create function private.create_tenant(p_name text, p_type text) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_uid uuid := (select auth.uid());
  v_id uuid;
begin
  if v_uid is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;
  if (select count(*) from public.memberships m where m.user_id = v_uid and m.role = 'owner') >= 5 then
    raise exception 'company limit reached' using errcode = 'LG409';
  end if;
  insert into public.tenants (name, type, created_by)
  values (btrim(p_name), p_type, v_uid)
  returning id into v_id;
  insert into public.memberships (tenant_id, user_id, role) values (v_id, v_uid, 'owner');
  perform private.write_audit('tenant.created', v_id, 'tenant', v_id::text,
                              jsonb_build_object('type', p_type));
  return v_id;
end
$$;

create function private.hash_invitation_token(p_token text) returns text
language sql immutable set search_path = '' as $$
  select encode(extensions.digest(convert_to(p_token, 'UTF8'), 'sha256'), 'hex');
$$;

-- What the invite page shows. Possessing the token is the authority to see this.
create function private.preview_invitation(p_token text)
returns table (tenant_name text, role text, email text, is_valid boolean)
language sql stable security definer set search_path = '' as $$
  select t.name,
         i.role,
         i.email::text,
         (i.accepted_at is null and i.revoked_at is null and i.expires_at > now()
          and t.status = 'active')
  from public.invitations i
  join public.tenants t on t.id = i.tenant_id
  where i.token_hash = private.hash_invitation_token(p_token);
$$;

create function private.accept_invitation(p_token text) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_uid uuid := (select auth.uid());
  v_email text;
  v_confirmed timestamptz;
  v_inv public.invitations%rowtype;
begin
  if v_uid is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;
  select u.email, u.email_confirmed_at into v_email, v_confirmed
  from auth.users u where u.id = v_uid;

  select * into v_inv
  from public.invitations i
  where i.token_hash = private.hash_invitation_token(p_token)
  for update;

  -- One generic message for every failure: never reveal which check failed.
  if not found
     or v_inv.accepted_at is not null
     or v_inv.revoked_at is not null
     or v_inv.expires_at <= now()
     or v_confirmed is null
     or lower(v_inv.email::text) <> lower(coalesce(v_email, ''))
     or not exists (select 1 from public.tenants t where t.id = v_inv.tenant_id and t.status = 'active')
  then
    raise exception 'invitation is invalid or has expired' using errcode = 'LG404';
  end if;

  insert into public.memberships (tenant_id, user_id, role)
  values (v_inv.tenant_id, v_uid, v_inv.role)
  on conflict (tenant_id, user_id) do nothing;

  update public.invitations
  set accepted_at = now(), accepted_by = v_uid
  where id = v_inv.id;

  perform private.write_audit('invitation.accepted', v_inv.tenant_id, 'invitation',
                              v_inv.id::text, jsonb_build_object('role', v_inv.role));
  return v_inv.tenant_id;
end
$$;

revoke all on all functions in schema private from public;
grant execute on function
  private.is_member(uuid),
  private.has_role(uuid, text[]),
  private.is_platform_admin(),
  private.session_is_active(),
  private.write_audit(text, uuid, text, text, jsonb),
  private.create_tenant(text, text),
  private.preview_invitation(text),
  private.accept_invitation(text),
  private.hash_invitation_token(text)
to authenticated;
grant execute on function
  private.is_member(uuid),
  private.has_role(uuid, text[]),
  private.hash_invitation_token(text)
to service_role;

-- ---------------------------------------------------------------------------
-- 7. Grants: nothing for anon; exactly what each path needs
-- ---------------------------------------------------------------------------
revoke all on public.tenants, public.memberships, public.platform_admins,
              public.invitations, public.audit_log
  from public, anon, authenticated, service_role;
revoke all on sequence public.audit_log_id_seq from public, anon, authenticated, service_role;

grant select, update (name, branding) on public.tenants to authenticated;
grant select, update (role), delete on public.memberships to authenticated;
grant select on public.platform_admins to authenticated;
grant select, insert (tenant_id, email, role, token_hash), update (revoked_at)
  on public.invitations to authenticated;
-- audit_log: no direct access for users; writes go through private.write_audit().

-- service_role is used only by system_db() (worker and admin module).
grant select, insert, update, delete on public.tenants, public.memberships, public.invitations
  to service_role;
grant select on public.platform_admins to service_role;   -- admins are created by SQL only
grant select, insert on public.audit_log to service_role;  -- append-only
grant usage on sequence public.audit_log_id_seq to service_role;

-- ---------------------------------------------------------------------------
-- 8. Row-level security: enabled and forced everywhere
-- ---------------------------------------------------------------------------
alter table public.tenants enable row level security;
alter table public.tenants force row level security;
alter table public.memberships enable row level security;
alter table public.memberships force row level security;
alter table public.platform_admins enable row level security;
alter table public.platform_admins force row level security;
alter table public.invitations enable row level security;
alter table public.invitations force row level security;
alter table public.audit_log enable row level security;
alter table public.audit_log force row level security;

-- tenants
create policy tenants_select on public.tenants for select to authenticated
  using (private.is_member(id));
create policy tenants_update on public.tenants for update to authenticated
  using (private.has_role(id, array['owner', 'admin']))
  with check (private.has_role(id, array['owner', 'admin']));

-- memberships: only an owner changes roles, and never their own row
create policy memberships_select on public.memberships for select to authenticated
  using (private.is_member(tenant_id));
create policy memberships_update on public.memberships for update to authenticated
  using (private.has_role(tenant_id, array['owner']) and user_id <> (select auth.uid()))
  with check (private.has_role(tenant_id, array['owner']) and user_id <> (select auth.uid()));
create policy memberships_delete on public.memberships for delete to authenticated
  using (
    (private.has_role(tenant_id, array['owner']) and user_id <> (select auth.uid()))
    or (user_id = (select auth.uid()) and role <> 'owner')  -- leave a company
  );

-- platform_admins: a user can see only their own row
create policy platform_admins_select_self on public.platform_admins for select to authenticated
  using (user_id = (select auth.uid()));

-- invitations: owners and admins of the company; admins may invite members only
create policy invitations_select on public.invitations for select to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));
create policy invitations_insert on public.invitations for insert to authenticated
  with check (
    invited_by = (select auth.uid())
    and (
      private.has_role(tenant_id, array['owner'])
      or (role = 'member' and private.has_role(tenant_id, array['admin']))
    )
  );
create policy invitations_update on public.invitations for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));

-- service_role bypasses RLS (system_db only); policies below document intent for audit_log.
-- audit_log has no policies for authenticated: users cannot read or write it directly.
