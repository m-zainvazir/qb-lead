-- Module 2: the per-company profile built from the questionnaire.
--
-- Built from supabase/templates/tenant_table.sql: tenant_id + index, RLS enabled and
-- forced, column-level UPDATE grants (never id / tenant_id / created_at).
-- Owners and admins edit; every member can read. Outputs of the compiler and of
-- portfolio processing are written by the worker (service_role) only.
--
-- Versioning: any change to the profile or its services, markets, signals or exclusions
-- bumps tenant_profiles.version once per transaction and marks the profile 'pending'.
-- The compiler job turns a pending version into search terms and fingerprints, so later
-- matches can record the version they used.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table public.tenant_profiles (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null unique references public.tenants (id) on delete restrict,
  type            text check (type in ('freelancer', 'agency')),
  team_size       integer check (team_size between 1 and 5000),
  min_budget_usd  integer check (min_budget_usd between 0 and 10000000),
  client_sizes    text[] not null default '{}'
                  check (client_sizes <@ array['solo', 'small', 'mid', 'enterprise']),
  tone            text check (tone in ('friendly', 'professional', 'direct')),
  priorities      text[] not null default '{}'
                  check (priorities <@ array['speed', 'quality', 'price', 'long_term']
                         and cardinality(priorities) <= 3),
  time_zone       text check (time_zone ~ '^[A-Za-z_]+(/[A-Za-z_+-]+){0,2}$' and char_length(time_zone) <= 64),
  about           text check (char_length(about) <= 2000),
  version         integer not null default 1,
  version_txid    bigint,
  compile_status  text not null default 'pending'
                  check (compile_status in ('pending', 'compiling', 'ready', 'failed')),
  compiled_version integer,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create table public.tenant_services (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references public.tenants (id) on delete restrict,
  service_id  uuid references public.services (id) on delete restrict,
  custom_name text check (char_length(btrim(custom_name)) between 2 and 80 and custom_name !~ '[[:cntrl:]]'),
  created_at  timestamptz not null default now(),
  check ((service_id is null) <> (custom_name is null))  -- catalogue OR a private custom service
);
create index tenant_services_tenant_id_idx on public.tenant_services (tenant_id);
create unique index tenant_services_catalogue_uniq on public.tenant_services (tenant_id, service_id)
  where service_id is not null;
create unique index tenant_services_custom_uniq on public.tenant_services (tenant_id, lower(custom_name))
  where custom_name is not null;

create table public.tenant_markets (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id) on delete restrict,
  market_id  uuid not null references public.markets (id) on delete restrict,
  weight     numeric(4, 2) check (weight between 0 and 1),  -- null = market default
  created_at timestamptz not null default now(),
  unique (tenant_id, market_id)
);

create table public.tenant_signals (
  id             uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null references public.tenants (id) on delete restrict,
  signal_type_id uuid not null references public.signal_types (id) on delete restrict,
  weight         numeric(4, 2) check (weight between 0 and 1),
  created_at     timestamptz not null default now(),
  unique (tenant_id, signal_type_id)
);

create table public.tenant_exclusions (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id) on delete restrict,
  kind       text not null default 'keyword' check (kind in ('keyword', 'industry', 'company')),
  value      text not null check (char_length(btrim(value)) between 1 and 200 and value !~ '[[:cntrl:]]'),
  created_at timestamptz not null default now()
);
create index tenant_exclusions_tenant_id_idx on public.tenant_exclusions (tenant_id);

create table public.onboarding_progress (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null unique references public.tenants (id) on delete restrict,
  current_step integer not null default 1 check (current_step between 1 and 20),
  answers      jsonb not null default '{}'::jsonb
               check (jsonb_typeof(answers) = 'object' and pg_column_size(answers) < 65536),
  completed_at timestamptz,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create table public.profile_compilations (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id) on delete restrict,
  profile_version integer not null,
  status          text not null default 'running' check (status in ('running', 'ready', 'failed')),
  search_terms    jsonb not null default '{}'::jsonb,
  embedding_model text,
  cost_usd        numeric(12, 6) not null default 0,
  error           text check (char_length(error) <= 2000),
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  unique (tenant_id, profile_version)
);

-- Vector size is fixed per model (docs/decisions/0002-embeddings.md). 384 = bge-small-en-v1.5.
create table public.service_fingerprints (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references public.tenants (id) on delete restrict,
  tenant_service_id uuid not null references public.tenant_services (id) on delete cascade,
  profile_version   integer not null,
  embedding_model   text not null,
  dims              integer not null check (dims = 384),
  embedding         extensions.vector(384) not null,
  source_text       text not null check (char_length(source_text) <= 8000),
  created_at        timestamptz not null default now(),
  unique (tenant_service_id, profile_version, embedding_model)
);
create index service_fingerprints_tenant_idx on public.service_fingerprints (tenant_id, profile_version);
create index service_fingerprints_embedding_idx on public.service_fingerprints
  using hnsw (embedding extensions.vector_cosine_ops);

create table public.portfolio_items (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references public.tenants (id) on delete restrict,
  title           text not null check (char_length(btrim(title)) between 1 and 200 and title !~ '[[:cntrl:]]'),
  file_path       text not null unique,
  mime_type       text not null check (mime_type in (
                    'application/pdf',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'text/plain')),
  size_bytes      integer not null check (size_bytes between 1 and 10485760),
  status          text not null default 'uploaded'
                  check (status in ('uploaded', 'processing', 'ready', 'failed')),
  summary         text check (char_length(summary) <= 2000),
  extracted_chars integer,
  embedding_model text,
  embedding       extensions.vector(384),
  error           text check (char_length(error) <= 2000),
  created_by      uuid default auth.uid() references auth.users (id) on delete set null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  -- a row can only point at a file inside its own company's folder
  check (split_part(file_path, '/', 1) = tenant_id::text and file_path !~ '\.\.')
);
create index portfolio_items_tenant_id_idx on public.portfolio_items (tenant_id, created_at desc);

create trigger tenant_profiles_touch before update on public.tenant_profiles
  for each row execute function private.touch_updated_at();
create trigger onboarding_progress_touch before update on public.onboarding_progress
  for each row execute function private.touch_updated_at();
create trigger portfolio_items_touch before update on public.portfolio_items
  for each row execute function private.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Versioning: bump once per transaction on any profile-defining change
-- ---------------------------------------------------------------------------
create function private.profile_before_update() returns trigger
language plpgsql set search_path = '' as $$
begin
  if (new.type, new.team_size, new.min_budget_usd, new.client_sizes, new.tone, new.priorities,
      new.time_zone, new.about)
     is distinct from
     (old.type, old.team_size, old.min_budget_usd, old.client_sizes, old.tone, old.priorities,
      old.time_zone, old.about)
     and old.version_txid is distinct from txid_current()
  then
    new.version := old.version + 1;
    new.version_txid := txid_current();
    new.compile_status := 'pending';
  end if;
  return new;
end
$$;
create trigger tenant_profiles_version before update on public.tenant_profiles
  for each row execute function private.profile_before_update();

create function private.bump_profile_version() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.tenant_profiles p
  set version = p.version + 1, version_txid = txid_current(), compile_status = 'pending'
  where p.tenant_id = coalesce(new.tenant_id, old.tenant_id)
    and p.version_txid is distinct from txid_current();
  return null;
end
$$;
create trigger tenant_services_version after insert or update or delete on public.tenant_services
  for each row execute function private.bump_profile_version();
create trigger tenant_markets_version after insert or update or delete on public.tenant_markets
  for each row execute function private.bump_profile_version();
create trigger tenant_signals_version after insert or update or delete on public.tenant_signals
  for each row execute function private.bump_profile_version();
create trigger tenant_exclusions_version after insert or update or delete on public.tenant_exclusions
  for each row execute function private.bump_profile_version();

-- ---------------------------------------------------------------------------
-- Grants: nothing for anon; users never write id, tenant_id, created_at or system columns
-- ---------------------------------------------------------------------------
revoke all on public.tenant_profiles, public.tenant_services, public.tenant_markets,
              public.tenant_signals, public.tenant_exclusions, public.onboarding_progress,
              public.profile_compilations, public.service_fingerprints, public.portfolio_items
  from public, anon, authenticated, service_role;

grant select,
      insert (tenant_id, type, team_size, min_budget_usd, client_sizes, tone, priorities, time_zone, about),
      update (type, team_size, min_budget_usd, client_sizes, tone, priorities, time_zone, about)
  on public.tenant_profiles to authenticated;
grant select, insert (tenant_id, service_id, custom_name), delete on public.tenant_services to authenticated;
grant select, insert (tenant_id, market_id, weight), update (weight), delete
  on public.tenant_markets to authenticated;
grant select, insert (tenant_id, signal_type_id, weight), update (weight), delete
  on public.tenant_signals to authenticated;
grant select, insert (tenant_id, kind, value), delete on public.tenant_exclusions to authenticated;
grant select, insert (tenant_id, current_step, answers), update (current_step, answers, completed_at)
  on public.onboarding_progress to authenticated;
grant select on public.profile_compilations, public.service_fingerprints to authenticated;
grant select (id, tenant_id, title, file_path, mime_type, size_bytes, status, summary,
              extracted_chars, error, created_by, created_at, updated_at),
      insert (tenant_id, title, file_path, mime_type, size_bytes),
      update (title), delete
  on public.portfolio_items to authenticated;

grant select, insert, update, delete on public.tenant_profiles, public.tenant_services,
      public.tenant_markets, public.tenant_signals, public.tenant_exclusions,
      public.onboarding_progress, public.profile_compilations, public.service_fingerprints,
      public.portfolio_items
  to service_role;

-- ---------------------------------------------------------------------------
-- Row-level security
-- ---------------------------------------------------------------------------
alter table public.tenant_profiles enable row level security;
alter table public.tenant_profiles force row level security;
alter table public.tenant_services enable row level security;
alter table public.tenant_services force row level security;
alter table public.tenant_markets enable row level security;
alter table public.tenant_markets force row level security;
alter table public.tenant_signals enable row level security;
alter table public.tenant_signals force row level security;
alter table public.tenant_exclusions enable row level security;
alter table public.tenant_exclusions force row level security;
alter table public.onboarding_progress enable row level security;
alter table public.onboarding_progress force row level security;
alter table public.profile_compilations enable row level security;
alter table public.profile_compilations force row level security;
alter table public.service_fingerprints enable row level security;
alter table public.service_fingerprints force row level security;
alter table public.portfolio_items enable row level security;
alter table public.portfolio_items force row level security;

-- Editable profile tables: members read, owners and admins write.
create policy tenant_profiles_select on public.tenant_profiles for select to authenticated
  using (private.is_member(tenant_id));
create policy tenant_profiles_insert on public.tenant_profiles for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_profiles_update on public.tenant_profiles for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));

create policy tenant_services_select on public.tenant_services for select to authenticated
  using (private.is_member(tenant_id));
create policy tenant_services_insert on public.tenant_services for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_services_delete on public.tenant_services for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

create policy tenant_markets_select on public.tenant_markets for select to authenticated
  using (private.is_member(tenant_id));
create policy tenant_markets_insert on public.tenant_markets for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_markets_update on public.tenant_markets for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_markets_delete on public.tenant_markets for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

create policy tenant_signals_select on public.tenant_signals for select to authenticated
  using (private.is_member(tenant_id));
create policy tenant_signals_insert on public.tenant_signals for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_signals_update on public.tenant_signals for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_signals_delete on public.tenant_signals for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

create policy tenant_exclusions_select on public.tenant_exclusions for select to authenticated
  using (private.is_member(tenant_id));
create policy tenant_exclusions_insert on public.tenant_exclusions for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_exclusions_delete on public.tenant_exclusions for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

create policy onboarding_progress_select on public.onboarding_progress for select to authenticated
  using (private.is_member(tenant_id));
create policy onboarding_progress_insert on public.onboarding_progress for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy onboarding_progress_update on public.onboarding_progress for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));

-- System-written outputs: members read only.
create policy profile_compilations_select on public.profile_compilations for select to authenticated
  using (private.is_member(tenant_id));
create policy service_fingerprints_select on public.service_fingerprints for select to authenticated
  using (private.is_member(tenant_id));

create policy portfolio_items_select on public.portfolio_items for select to authenticated
  using (private.is_member(tenant_id));
create policy portfolio_items_insert on public.portfolio_items for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy portfolio_items_update on public.portfolio_items for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy portfolio_items_delete on public.portfolio_items for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));
