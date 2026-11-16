# Runbook

Short notes on how to start, stop, deploy, roll back and debug.

Since 2026-11-15 there is **no local Supabase or Postgres**. The API, worker, scheduler, Redis, Mailpit and the web dev server run on your machine; the database, login and storage are the hosted Supabase **staging** project (ref `djwfqlzrskxeudzttvhx`, US East, Free plan). Production will be a separate project. See `docs/decisions/0004-hosted-staging-dev.md`.

## First run on a new machine

Needs Docker Desktop, Node 20+, Python 3.12, `uv`, `make` (`winget install ezwinports.make`) and `gitleaks` (`winget install Gitleaks.Gitleaks`).

```
make install          # uv sync + npm install (root and apps/web)
git config core.hooksPath .githooks
make dev              # API/worker/scheduler/Redis/Mailpit containers, then the web dev server
```

Before the first run, fill the env files by hand (they are never committed):

- `.env` from `.env.example`. From the Supabase dashboard: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`; `DATABASE_URL_ADMIN` is the **Session pooler** string (`postgres.<ref>@aws-1-us-east-1.pooler.supabase.com:5432`, with `?sslmode=require`). `DATABASE_URL_API` / `DATABASE_URL_SYSTEM` use the same host with the logins `app_api.<ref>` / `app_system.<ref>` and the passwords in `APP_DB_PASSWORD` / `SYSTEM_DB_PASSWORD`. `APP_ENV=staging`.
- `apps/web/.env.local`: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (same values as `.env`), `API_URL=http://localhost:8000`, `WEB_BASE_URL=http://localhost:3000`.
- Then `make push-staging` (migrations) and `make db-roles` (app login passwords), once per new project.

| What | Where |
| --- | --- |
| Web | http://localhost:3000 |
| API health | http://localhost:8000/healthz |
| API docs (local only) | http://localhost:8000/docs |
| Supabase dashboard | https://supabase.com/dashboard/project/djwfqlzrskxeudzttvhx |
| Test inbox (Mailpit, invitation emails) | http://127.0.0.1:54324 |
| SQL | `make psql sql="select 1"` |

## Start and stop

- `make dev` starts everything. `make up` restarts only the backend containers.
- `make stop` stops the local containers. Staging data is not touched.
- `make logs` follows the API, worker and scheduler logs. Every log line is JSON with a `request_id`.

## Database

- New migration: `npx supabase migration new <name>`. For a table holding customer data, start from `supabase/templates/tenant_table.sql` (`make migration-tenant name=<table>`).
- Apply new migrations to staging: `make push-staging` (dry run, then apply). It refuses any project not listed in `.claude/staging-targets.txt` and anything in `.claude/protected-targets.txt`. Typing the Supabase CLI's push or link commands directly is blocked by the guard hook.
- There is no database reset. Staging is never reset from here; to start over, create a new staging project.
- Never edit a pushed migration. Write a new one.
- Staging is shared test data: tests and `make seed-test` write fake companies (Agency A/B) there. Never put real customer data in staging.

## Tenants, logins and isolation (module 1)

- Two DB login roles: `app_api` (user requests, RLS applies) and `app_system` (worker and admin only). See `docs/decisions/0001-db-access.md`.
- Test data: `make seed-test` creates Agency A (owner, member), Agency B (owner) and a platform admin with TOTP on staging, and writes `.env.test.local` (tokens last 15 minutes).
- Isolation checks: `make test-isolation`, or the full terminal tests with `bash scripts/rls_terminal_tests.sh` (or the `rls-test` skill).
- New tenant table: `make migration-tenant name=<table>`, then add a factory in `tests/isolation/factories.py`; the suite fails until you do.
- First platform admin: `supabase/snippets/create_platform_admin.sql` (SQL only, never a screen). The admin then enrols an authenticator at `/admin/mfa`; admin routes need aal2.
- Someone locked out of a company: check `memberships` and the company's `status` (members of suspended companies see nothing).
- "A company must keep at least one owner": promote another member to owner first.
- Audit entries for memberships, invitations and companies are written by database triggers, so changes through the Supabase REST API are logged too. Revoking an invitation goes through `private.revoke_invitation()`.
- The Supabase REST API refuses tokens of ended sessions via `pgrst.db_pre_request = private.check_request` (set on the `authenticator` role by migration). On hosted Supabase, check it is set after the first deploy: `select rolconfig from pg_roles where rolname = 'authenticator';`
- Who did what: `select * from audit_log where tenant_id = '<id>' order by occurred_at desc limit 50;` (append-only; entries cannot be edited or deleted).

## Debugging

- "Database pools are not open": the API started without its lifespan; check `make logs` for a settings error at startup.
- A missing setting fails startup with a pydantic `ValidationError` that names the variable.
- Scheduler: exactly one `scheduler` container. Never scale it.

## Staging and production

Not set up yet (module 0's staging step is deferred). When it is:

- Add the production project ref and host to `.claude/protected-targets.txt`.
- Create the `app_api` / `app_system` passwords per environment (`python -m api.cli db-roles` with that environment's values, from a machine allowed to reach it), and set `SUPABASE_JWT_ISSUER` if the API reaches Supabase on a different host than the public URL.
- Run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>` so audit entries record the real client IP.
- Copy the email templates (`supabase/templates/email/*.html`) into the hosted project, and set Site URL and redirect URLs.
- Turn on leaked-password protection (HIBP) and MFA in the hosted Supabase Auth settings.
- Enable database backups before any real data arrives.
