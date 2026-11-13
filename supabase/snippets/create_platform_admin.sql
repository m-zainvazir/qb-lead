-- Make an existing user a platform admin. Run by hand, as the database owner, never
-- from a screen or the API:
--
--   docker exec -i supabase_db_leadgen psql -U postgres -d postgres \
--     -v email="'you@example.com'" -v level="'super'" < supabase/snippets/create_platform_admin.sql
--
-- On staging/production, run it in the Supabase SQL editor with the values filled in.
-- The admin must then enrol an authenticator app at /admin/mfa: admin routes require aal2.

insert into public.platform_admins (user_id, level)
select u.id, :level
from auth.users u
where u.email = :email
on conflict (user_id) do update set level = excluded.level
returning user_id, level, created_by;
