-- Module 1 hardening after the security review (docs/reviews/2026-11-13-module-01.md).
--
-- 1. Invitations: no direct UPDATE (an admin could un-revoke an owner's admin invitation).
--    Revoking goes through private.revoke_invitation(); admins manage member invitations only.
-- 2. Audit entries are written by triggers, so changes made through the Supabase REST API
--    are logged exactly like changes made through our API.
-- 3. Invitation limits (daily cap, already a member, one open per email) live in the
--    database, so REST callers cannot skip them. Advisory locks make the caps race-free.
-- 4. Revoked sessions are refused on the REST path too (PostgREST pre-request hook).
-- 5. The last-owner check locks the company row, so two owners cannot demote each other
--    at the same moment.
-- 6. Company names cannot contain control characters (they end up in email headers).

-- ---------------------------------------------------------------------------
-- 1. Invitations: revoke through a function only
-- ---------------------------------------------------------------------------
revoke update on public.invitations from authenticated;
drop policy invitations_update on public.invitations;

create function private.can_manage_invitation(p_tenant_id uuid, p_role text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.has_role(p_tenant_id, array['owner'])
      or (p_role = 'member' and private.has_role(p_tenant_id, array['admin']));
$$;

create function private.revoke_invitation(p_invitation_id uuid) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_tenant uuid;
begin
  update public.invitations i
  set revoked_at = now()
  where i.id = p_invitation_id
    and i.accepted_at is null
    and i.revoked_at is null
    and private.can_manage_invitation(i.tenant_id, i.role)
  returning i.tenant_id into v_tenant;
  if v_tenant is null then
    raise exception 'invitation not found' using errcode = 'LG404';
  end if;
  return v_tenant;
end
$$;

-- Before a new invitation: daily cap, not already a member, replace an open one if allowed.
create function private.invitations_before_insert() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- BEFORE triggers run ahead of the RLS insert check. Refuse callers who may not invite
  -- here first, so the checks below can never tell them anything about another company.
  if (select auth.uid()) is not null and not private.can_manage_invitation(new.tenant_id, new.role) then
    raise exception 'new row violates row-level security policy for table "invitations"'
      using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('invitations:' || new.tenant_id::text, 0));

  if (select count(*) from public.invitations i
      where i.tenant_id = new.tenant_id and i.created_at > now() - interval '1 day') >= 50 then
    raise exception 'daily invitation limit reached' using errcode = 'LG429';
  end if;

  if exists (
    select 1 from public.memberships m join auth.users u on u.id = m.user_id
    where m.tenant_id = new.tenant_id and lower(u.email) = lower(new.email::text)
  ) then
    raise exception 'that person is already a member' using errcode = 'LG409';
  end if;

  if exists (
    select 1 from public.invitations i
    where i.tenant_id = new.tenant_id and i.email = new.email
      and i.accepted_at is null and i.revoked_at is null
      and not private.can_manage_invitation(i.tenant_id, i.role)
  ) then
    raise exception 'an invitation for this email is already open' using errcode = 'LG409';
  end if;

  update public.invitations i
  set revoked_at = now()
  where i.tenant_id = new.tenant_id and i.email = new.email
    and i.accepted_at is null and i.revoked_at is null;
  return new;
end
$$;
create trigger invitations_before_insert before insert on public.invitations
  for each row execute function private.invitations_before_insert();

-- ---------------------------------------------------------------------------
-- 2. Audit entries from triggers (every path: our API, Supabase REST, the worker)
-- ---------------------------------------------------------------------------
create function private.audit_insert(
  p_action text, p_tenant_id uuid, p_target_type text, p_target_id text, p_metadata jsonb
) returns void
language plpgsql security definer set search_path = '' as $$
declare
  v_uid uuid := (select auth.uid());
begin
  insert into public.audit_log (actor_user_id, actor_kind, tenant_id, action, target_type,
                                target_id, metadata, request_id, ip)
  values (v_uid, case when v_uid is null then 'system' else 'user' end, p_tenant_id, p_action,
          p_target_type, p_target_id, coalesce(p_metadata, '{}'::jsonb),
          nullif(current_setting('app.request_id', true), ''),
          nullif(current_setting('app.client_ip', true), '')::inet);
end
$$;
revoke all on function private.audit_insert(text, uuid, text, text, jsonb) from public;

create function private.audit_memberships() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    perform private.audit_insert('membership.added', new.tenant_id, 'user', new.user_id::text,
                                 jsonb_build_object('role', new.role));
  elsif tg_op = 'UPDATE' and new.role is distinct from old.role then
    perform private.audit_insert('membership.role_changed', new.tenant_id, 'user',
                                 new.user_id::text,
                                 jsonb_build_object('from', old.role, 'to', new.role));
  elsif tg_op = 'DELETE' then
    perform private.audit_insert(
      case when old.user_id = (select auth.uid()) then 'membership.left' else 'membership.removed' end,
      old.tenant_id, 'user', old.user_id::text, jsonb_build_object('role', old.role));
  end if;
  return null;
end
$$;
create trigger memberships_audit after insert or update or delete on public.memberships
  for each row execute function private.audit_memberships();

create function private.audit_invitations() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    perform private.audit_insert('invitation.created', new.tenant_id, 'invitation', new.id::text,
                                 jsonb_build_object('role', new.role));
  elsif old.revoked_at is null and new.revoked_at is not null then
    perform private.audit_insert('invitation.revoked', new.tenant_id, 'invitation', new.id::text,
                                 jsonb_build_object('role', new.role));
  elsif old.accepted_at is null and new.accepted_at is not null then
    perform private.audit_insert('invitation.accepted', new.tenant_id, 'invitation', new.id::text,
                                 jsonb_build_object('role', new.role));
  end if;
  return null;
end
$$;
create trigger invitations_audit after insert or update on public.invitations
  for each row execute function private.audit_invitations();

create function private.audit_tenants() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  v_changed text[] := array[]::text[];
begin
  if tg_op = 'INSERT' then
    perform private.audit_insert('tenant.created', new.id, 'tenant', new.id::text,
                                 jsonb_build_object('type', new.type));
    return null;
  end if;
  if new.name is distinct from old.name then v_changed := v_changed || 'name'; end if;
  if new.branding is distinct from old.branding then v_changed := v_changed || 'branding'; end if;
  if new.status is distinct from old.status then v_changed := v_changed || 'status'; end if;
  if new.is_internal is distinct from old.is_internal then v_changed := v_changed || 'is_internal'; end if;
  if new.custom_domain is distinct from old.custom_domain then v_changed := v_changed || 'custom_domain'; end if;
  if cardinality(v_changed) > 0 then
    perform private.audit_insert('tenant.updated', new.id, 'tenant', new.id::text,
                                 jsonb_build_object('changed', v_changed, 'status', new.status));
  end if;
  return null;
end
$$;
create trigger tenants_audit after insert or update on public.tenants
  for each row execute function private.audit_tenants();

-- The RPCs no longer write their own entries (the triggers do), and create_tenant takes a
-- per-user lock so the company cap cannot be raced.
create or replace function private.create_tenant(p_name text, p_type text) returns uuid
language plpgsql volatile security definer set search_path = '' as $$
declare
  v_uid uuid := (select auth.uid());
  v_id uuid;
begin
  if v_uid is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('create_tenant:' || v_uid::text, 0));
  if (select count(*) from public.memberships m where m.user_id = v_uid and m.role = 'owner') >= 5 then
    raise exception 'company limit reached' using errcode = 'LG409';
  end if;
  insert into public.tenants (name, type, created_by)
  values (btrim(p_name), p_type, v_uid)
  returning id into v_id;
  insert into public.memberships (tenant_id, user_id, role) values (v_id, v_uid, 'owner');
  return v_id;
end
$$;

create or replace function private.accept_invitation(p_token text) returns uuid
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
  return v_inv.tenant_id;
end
$$;

-- ---------------------------------------------------------------------------
-- 3. Last owner: serialise owner changes per company
-- ---------------------------------------------------------------------------
create or replace function private.keep_one_owner() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if old.role = 'owner' and (tg_op = 'DELETE' or new.role <> 'owner') then
    perform 1 from public.tenants t where t.id = old.tenant_id for update;
    if exists (select 1 from public.tenants t where t.id = old.tenant_id and t.status <> 'deleted')
       and not exists (
         select 1 from public.memberships m
         where m.tenant_id = old.tenant_id and m.role = 'owner' and m.id <> old.id
       )
    then
      raise exception 'a company must keep at least one owner' using errcode = 'LG409';
    end if;
  end if;
  return coalesce(new, old);
end
$$;

-- ---------------------------------------------------------------------------
-- 4. Supabase REST: refuse tokens whose session has ended (sign-out everywhere, reset)
-- ---------------------------------------------------------------------------
create function private.check_request() returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if coalesce((select auth.jwt() ->> 'role'), '') = 'authenticated'
     and not private.session_is_active() then
    raise sqlstate 'PGRST' using
      message = json_build_object('code', 'session_ended', 'message', 'Session has ended')::text,
      detail = json_build_object('status', 401, 'headers', json_build_object())::text;
  end if;
end
$$;
revoke all on function private.check_request() from public;
grant usage on schema private to anon;
grant execute on function private.check_request() to anon, authenticated, service_role;
alter role authenticator set pgrst.db_pre_request = 'private.check_request';
notify pgrst, 'reload config';

-- ---------------------------------------------------------------------------
-- 5. Company names: no control characters
-- ---------------------------------------------------------------------------
alter table public.tenants
  add constraint tenants_name_printable check (name !~ '[[:cntrl:]]');

-- New functions: execute rights
revoke all on function private.can_manage_invitation(uuid, text) from public;
revoke all on function private.revoke_invitation(uuid) from public;
grant execute on function private.can_manage_invitation(uuid, text) to authenticated;
grant execute on function private.revoke_invitation(uuid) to authenticated;
