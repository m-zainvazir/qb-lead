-- Module 1: team list with email addresses.
-- `authenticated` cannot read auth.users, so this definer function returns the members
-- of one company, and only to someone who is a member of that company.

create function private.team_members(p_tenant_id uuid)
returns table (user_id uuid, email text, role text, joined_at timestamptz)
language sql stable security definer set search_path = '' as $$
  select m.user_id, u.email::text, m.role, m.created_at
  from public.memberships m
  join auth.users u on u.id = m.user_id
  where m.tenant_id = p_tenant_id
    and private.is_member(p_tenant_id)
  order by m.created_at, m.user_id;
$$;

revoke all on function private.team_members(uuid) from public;
grant execute on function private.team_members(uuid) to authenticated;
