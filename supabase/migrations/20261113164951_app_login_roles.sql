-- Login roles for the backend. See docs/decisions/0001-db-access.md.
--
-- app_api    -> user_db(): may only act as `authenticated` (row-level security applies).
-- app_system -> system_db(): may act as `service_role` (bypasses RLS). Worker and admin only.
--
-- Both are NOINHERIT and get their membership WITH INHERIT FALSE, so a bare connection
-- holds no table privileges at all. Every transaction must SET LOCAL ROLE first.
-- No passwords here: `python -m api.cli db-roles` sets them from the environment.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_api') then
    create role app_api login noinherit nosuperuser nocreatedb nocreaterole nobypassrls noreplication;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'app_system') then
    create role app_system login noinherit nosuperuser nocreatedb nocreaterole nobypassrls noreplication;
  end if;
end
$$;

grant authenticated to app_api with inherit false, set true;
grant service_role to app_system with inherit false, set true;

-- A connection limit keeps a runaway pool from starving the database.
alter role app_api connection limit 40;
alter role app_system connection limit 20;
