# 0004: Develop against a hosted Supabase staging project (no local Supabase)

Date: 2026-11-16. Status: accepted (the user's decision, 2026-11-15).

## Context

Modules 0 to 3 were built against the local Supabase CLI stack. Before module 4 the user
wanted the hosted platform's differences found early (connection pooler, a non-superuser
`postgres`, auth email limits, signing keys), while there are only three modules built on
top, and asked for local Supabase and Postgres to be removed from the machine completely.

## Decision

- One hosted Supabase project is **staging**: ref `djwfqlzrskxeudzttvhx`, US East
  (N. Virginia), Free plan, Postgres 17, ES256 signing keys. It holds fake test data only.
- The API, worker, scheduler, Redis, Mailpit and the web dev server still run locally;
  only the database, login and storage are hosted.
- Database connections go through the Supavisor **session** pooler
  (`aws-1-us-east-1.pooler.supabase.com:5432`, logins `<role>.<ref>`), because the direct
  connection is IPv6-only on the Free plan. Session mode keeps prepared statements and
  `SET LOCAL ROLE` working exactly as before, so `core/db.py` is unchanged.
- `core.targets` decides what tests, `make seed-test`, `scripts/psql.py` and
  `make push-staging` may touch: a local stack or a ref in `.claude/staging-targets.txt`.
  `APP_ENV=production` and anything in `.claude/protected-targets.txt` are refused.
- Migrations reach staging only through `make push-staging`. Typing the CLI's push or link
  commands directly stays blocked by the guard hook. Staging is never reset from here.
- Production will be a separate project in the same Supabase organization, created near
  launch, and its ref goes into `.claude/protected-targets.txt` on day one.

## Findings on first push (2026-11-16)

All 14 migrations applied unchanged. On hosted Supabase: the `app_api` / `app_system` /
`ingest` role memberships (INHERIT FALSE, SET TRUE) work, the `authenticator`
pre-request check is set, `private.session_is_active()` can read `auth.sessions`, and
every public table has row-level security.

## Consequences

- Every query crosses the internet, so the isolation suite takes minutes, not seconds.
- The Free plan pauses after about a week without use (resume in the dashboard) and has
  no backups; the built-in auth email sends only a few messages an hour.
- Session pooler connections are limited per role; if the API or worker run out, move
  them to the transaction pooler (port 6543) and set `prepare_threshold=None` in `db.py`.
- Leaked-password protection (HIBP) needs a paid plan; it is a production task.
- Auth settings (password rules, token expiry, MFA, redirect URLs, email templates) are
  set in the dashboard, not by `supabase/config.toml`, which now only documents them.
