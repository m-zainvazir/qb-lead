-- Module 1: read helpers for the platform admin module (system_db / service_role only).
-- service_role cannot read auth.users directly; this exposes just id, email and role
-- for the members of one company.

create function private.admin_tenant_members(p_tenant_id uuid)
returns table (user_id uuid, email text, role text, joined_at timestamptz, last_sign_in_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select m.user_id, u.email::text, m.role, m.created_at, u.last_sign_in_at
  from public.memberships m
  join auth.users u on u.id = m.user_id
  where m.tenant_id = p_tenant_id
  order by m.created_at, m.user_id;
$$;

revoke all on function private.admin_tenant_members(uuid) from public, anon, authenticated;
grant execute on function private.admin_tenant_members(uuid) to service_role;
