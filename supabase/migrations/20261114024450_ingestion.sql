-- Module 3: sources and ingestion.
--
-- Connectors only collect. They write raw_items; module 4 reads and judges them.
--   * sources, source_runs, fetch_guard_events: platform data (worker/admin only)
--   * raw_items: 'pooled' rows (shared engine, no tenant) are invisible to customers;
--     'private' rows (a company's own webhook or email) are visible to that company only
--   * tenant_sources, inbound_endpoints: per company

-- ---------------------------------------------------------------------------
-- Sources and runs
-- ---------------------------------------------------------------------------
create table public.sources (
  key               text primary key check (key ~ '^[a-z][a-z0-9_]{1,40}$'),
  name              text not null check (char_length(btrim(name)) between 1 and 120),
  connector         text not null check (connector ~ '^[a-z][a-z0-9_]{1,40}$'),
  kind              text not null default 'pull' check (kind in ('pull', 'push')),
  risk              text not null check (risk in ('green', 'amber', 'red')),
  enabled           boolean not null default false,
  schedule_seconds  integer check (schedule_seconds is null or schedule_seconds >= 60),
  monthly_cap_usd   numeric(10, 2) not null default 0 check (monthly_cap_usd >= 0),
  cost_per_call_usd numeric(10, 6) not null default 0 check (cost_per_call_usd >= 0),
  rate_limit_per_minute integer not null default 30 check (rate_limit_per_minute between 1 and 6000),
  max_queries_per_run integer not null default 20 check (max_queries_per_run between 1 and 500),
  settings          jsonb not null default '{}'::jsonb check (jsonb_typeof(settings) = 'object'),
  red_override_by   uuid references auth.users (id) on delete set null,
  red_override_at   timestamptz,
  last_run_at       timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  -- a red source can only be enabled with a recorded platform admin override
  check (risk <> 'red' or not enabled or red_override_at is not null)
);

create table public.source_runs (
  id          uuid primary key default gen_random_uuid(),
  source_key  text not null references public.sources (key) on update cascade,
  status      text not null default 'running'
              check (status in ('running', 'succeeded', 'failed', 'capped', 'skipped')),
  trigger     text not null default 'schedule' check (trigger in ('schedule', 'manual', 'cli')),
  queries     integer not null default 0,
  fetched     integer not null default 0,
  new_items   integer not null default 0,
  cost_usd    numeric(12, 6) not null default 0,
  error       text check (char_length(error) <= 2000),
  started_at  timestamptz not null default now(),
  finished_at timestamptz
);
create index source_runs_source_idx on public.source_runs (source_key, started_at desc);

-- ---------------------------------------------------------------------------
-- Raw items
-- ---------------------------------------------------------------------------
create table public.raw_items (
  id           uuid primary key default gen_random_uuid(),
  source_key   text not null references public.sources (key) on update cascade,
  external_id  text not null check (char_length(external_id) between 1 and 300),
  visibility   text not null check (visibility in ('pooled', 'private')),
  tenant_id    uuid references public.tenants (id) on delete restrict,
  run_id       uuid references public.source_runs (id) on delete set null,
  url          text check (char_length(url) <= 2000),
  author_handle text check (char_length(author_handle) <= 200),
  author_url   text check (char_length(author_url) <= 2000),
  title        text check (char_length(title) <= 500),
  body         text check (char_length(body) <= 50000),
  posted_at    timestamptz,
  payload      jsonb not null default '{}'::jsonb check (pg_column_size(payload) < 262144),
  fetched_at   timestamptz not null default now(),
  expires_at   timestamptz not null default (now() + interval '90 days'),  -- raw payload retention
  unique (source_key, external_id),
  check ((visibility = 'private') = (tenant_id is not null))
);
create index raw_items_tenant_id_idx on public.raw_items (tenant_id, fetched_at desc);
create index raw_items_fetched_idx on public.raw_items (fetched_at desc);
create index raw_items_expires_idx on public.raw_items (expires_at);

-- ---------------------------------------------------------------------------
-- Per-company settings and inbound endpoints
-- ---------------------------------------------------------------------------
create table public.tenant_sources (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id) on delete restrict,
  source_key text not null references public.sources (key) on update cascade,
  enabled    boolean not null default true,
  created_at timestamptz not null default now(),
  unique (tenant_id, source_key)
);

create table public.inbound_endpoints (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references public.tenants (id) on delete restrict,
  kind         text not null check (kind in ('webhook', 'email')),
  token_hash   text not null unique check (token_hash ~ '^[0-9a-f]{64}$'),
  token_hint   text not null check (char_length(token_hint) between 4 and 12),  -- shown in screens
  email_local  text unique check (email_local ~ '^[a-z0-9][a-z0-9.-]{5,63}$'),
  created_by   uuid default auth.uid() references auth.users (id) on delete set null,
  created_at   timestamptz not null default now(),
  revoked_at   timestamptz,
  check ((kind = 'email') = (email_local is not null))
);
create index inbound_endpoints_tenant_id_idx on public.inbound_endpoints (tenant_id);

-- ---------------------------------------------------------------------------
-- Guarded fetcher log (blocked or failed fetches of links taken from outside content)
-- ---------------------------------------------------------------------------
create table public.fetch_guard_events (
  id          bigint generated always as identity primary key,
  url         text not null check (char_length(url) <= 2000),
  outcome     text not null check (outcome in ('blocked', 'error', 'fetched')),
  reason      text check (char_length(reason) <= 500),
  raw_item_id uuid references public.raw_items (id) on delete set null,
  created_at  timestamptz not null default now()
);
create index fetch_guard_events_created_idx on public.fetch_guard_events (created_at desc);

-- ---------------------------------------------------------------------------
-- usage_events: link to runs and sources; `ts` as the plan's query names it
-- ---------------------------------------------------------------------------
alter table public.usage_events
  add column run_id uuid references public.source_runs (id) on delete set null,
  add column source_key text references public.sources (key) on update cascade,
  add column ts timestamptz generated always as (created_at) stored;
create index usage_events_source_month_idx on public.usage_events (source_key, created_at);

create trigger sources_touch before update on public.sources
  for each row execute function private.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Grants and row-level security
-- ---------------------------------------------------------------------------
revoke all on public.sources, public.source_runs, public.raw_items, public.tenant_sources,
              public.inbound_endpoints, public.fetch_guard_events
  from public, anon, authenticated, service_role;
revoke all on sequence public.fetch_guard_events_id_seq from public, anon, authenticated, service_role;

grant select (id, source_key, external_id, visibility, tenant_id, url, author_handle, author_url,
              title, body, posted_at, fetched_at)
  on public.raw_items to authenticated;
grant select, insert (tenant_id, source_key, enabled), update (enabled), delete
  on public.tenant_sources to authenticated;
grant select (id, tenant_id, kind, token_hint, email_local, created_at, revoked_at)
  on public.inbound_endpoints to authenticated;

grant select, insert, update, delete on public.sources, public.source_runs, public.raw_items,
      public.tenant_sources, public.inbound_endpoints
  to service_role;
grant select, insert on public.fetch_guard_events to service_role;
grant usage on sequence public.fetch_guard_events_id_seq to service_role;

alter table public.sources enable row level security;
alter table public.sources force row level security;
alter table public.source_runs enable row level security;
alter table public.source_runs force row level security;
alter table public.raw_items enable row level security;
alter table public.raw_items force row level security;
alter table public.tenant_sources enable row level security;
alter table public.tenant_sources force row level security;
alter table public.inbound_endpoints enable row level security;
alter table public.inbound_endpoints force row level security;
alter table public.fetch_guard_events enable row level security;
alter table public.fetch_guard_events force row level security;

-- Pooled rows have tenant_id null, so is_member() is false for them: customers never
-- read the shared pool directly. A company reads only its own private items.
create policy raw_items_select on public.raw_items for select to authenticated
  using (visibility = 'private' and private.is_member(tenant_id));

create policy tenant_sources_select on public.tenant_sources for select to authenticated
  using (private.is_member(tenant_id));
create policy tenant_sources_insert on public.tenant_sources for insert to authenticated
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_sources_update on public.tenant_sources for update to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']))
  with check (private.has_role(tenant_id, array['owner', 'admin']));
create policy tenant_sources_delete on public.tenant_sources for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

create policy inbound_endpoints_select on public.inbound_endpoints for select to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

-- sources, source_runs, fetch_guard_events: no user policies (admin panel uses system_db).

-- ---------------------------------------------------------------------------
-- Seed the sources (all off by default; risk levels are in docs/sources.md)
-- ---------------------------------------------------------------------------
insert into public.sources (key, name, connector, kind, risk, enabled, schedule_seconds,
                            monthly_cap_usd, cost_per_call_usd, rate_limit_per_minute,
                            max_queries_per_run, settings)
values
  ('hackernews', 'Hacker News', 'hackernews', 'pull', 'green', true, 1800, 0, 0, 60, 30,
   '{"include_hiring_threads": true}'),
  ('web_exa', 'Web search (Exa)', 'web_exa', 'pull', 'green', false, 21600, 20, 0.005, 30, 20, '{}'),
  ('web_tavily', 'Web search (Tavily)', 'web_tavily', 'pull', 'green', false, 21600, 20, 0.008, 30, 20, '{}'),
  ('web_serper', 'Web search (Serper)', 'web_serper', 'pull', 'green', false, 21600, 10, 0.001, 30, 20, '{}'),
  ('webhook', 'Inbound webhook', 'webhook', 'push', 'green', true, null, 0, 0, 60, 1, '{}'),
  ('email', 'Inbound email', 'email', 'push', 'green', true, null, 0, 0, 60, 1, '{}'),
  ('fake', 'Fake source (tests)', 'fake', 'pull', 'green', false, null, 1, 0.001, 600, 50, '{}');
