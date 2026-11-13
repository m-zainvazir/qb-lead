-- Make an existing user a platform admin. Run by hand, as the database owner, never
-- from a screen or the API:
--
--   docker exec -i supabase_db_leadgen psql -U postgres -d postgres \
--     -v email="'you@example.com'" -v level="'super'" < supabase/snippets/create_platform_admin.sql
--
-- On staging/production, run it in the Supabase SQL editor with the values filled in.
-- The person must FIRST enrol an authenticator app at /admin/mfa (any signed-in user can):
-- the insert below does nothing for a user without a verified TOTP factor, so a stolen
-- password alone can never be used to set up admin access.

insert into public.platform_admins (user_id, level)
select u.id, :level
from auth.users u
where u.email = :email
  and exists (
    select 1 from auth.mfa_factors f
    where f.user_id = u.id and f.factor_type = 'totp' and f.status = 'verified'
  )
on conflict (user_id) do update set level = excluded.level
returning user_id, level, created_by;
