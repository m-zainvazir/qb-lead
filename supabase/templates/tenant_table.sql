-- Tenant table: __TABLE__
-- Generated from supabase/templates/tenant_table.sql by `make migration-tenant name=__TABLE__`.
-- Add your columns, then keep every block below. The isolation suite (tests/isolation)
-- finds this table by its tenant_id column and fails CI until it has a factory in
-- tests/isolation/factories.py.

create table public.__TABLE__ (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references public.tenants (id) on delete restrict,
  -- your columns here
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index __TABLE___tenant_id_idx on public.__TABLE__ (tenant_id);

create trigger __TABLE___touch before update on public.__TABLE__
  for each row execute function private.touch_updated_at();

-- Grants: nothing for anon. Users may never update id, tenant_id or created_at:
-- list the writable columns in the UPDATE grant (the isolation suite checks this).
revoke all on public.__TABLE__ from public, anon, authenticated, service_role;
grant select, insert, update (updated_at /* , your writable columns */), delete
  on public.__TABLE__ to authenticated;
grant select, insert, update, delete on public.__TABLE__ to service_role;

alter table public.__TABLE__ enable row level security;
alter table public.__TABLE__ force row level security;

create policy __TABLE___select on public.__TABLE__ for select to authenticated
  using (private.is_member(tenant_id));
create policy __TABLE___insert on public.__TABLE__ for insert to authenticated
  with check (private.is_member(tenant_id));
create policy __TABLE___update on public.__TABLE__ for update to authenticated
  using (private.is_member(tenant_id))
  with check (private.is_member(tenant_id));
-- Deleting needs an owner or admin; loosen only with a written reason.
create policy __TABLE___delete on public.__TABLE__ for delete to authenticated
  using (private.has_role(tenant_id, array['owner', 'admin']));
