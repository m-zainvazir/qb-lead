-- Module 2: usage and cost of every paid (or metered) outside call, written by metered_call().
-- Owners and admins can read their company's usage; only the worker/admin path writes.
-- Module 10 adds monthly caps on top of this table.

create table public.usage_events (
  id          bigint generated always as identity primary key,
  tenant_id   uuid references public.tenants (id) on delete restrict,  -- null = platform-level
  provider    text not null check (char_length(provider) between 1 and 60),
  operation   text not null check (char_length(operation) between 1 and 80),
  units       numeric(14, 2) not null default 0 check (units >= 0),
  unit        text not null default 'call' check (char_length(unit) between 1 and 30),
  cost_usd    numeric(12, 6) not null default 0 check (cost_usd >= 0),
  succeeded   boolean not null default true,
  duration_ms integer check (duration_ms >= 0),
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index usage_events_tenant_id_idx on public.usage_events (tenant_id, created_at desc);

revoke all on public.usage_events from public, anon, authenticated, service_role;
revoke all on sequence public.usage_events_id_seq from public, anon, authenticated, service_role;
grant select on public.usage_events to authenticated;
grant select, insert on public.usage_events to service_role;
grant usage on sequence public.usage_events_id_seq to service_role;

alter table public.usage_events enable row level security;
alter table public.usage_events force row level security;

create policy usage_events_select on public.usage_events for select to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));

-- The first save of a profile is version 1 (the insert stamps the transaction, so the
-- same transaction's service/market/signal inserts do not bump it again).
create function private.profile_before_insert() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.version := 1;
  new.version_txid := txid_current();
  new.compile_status := 'pending';
  return new;
end
$$;
create trigger tenant_profiles_version_insert before insert on public.tenant_profiles
  for each row execute function private.profile_before_insert();
