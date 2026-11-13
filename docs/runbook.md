# Runbook

Short notes on how to start, stop, deploy, roll back and debug. Local only for now; staging and production sections are filled in when they exist.

## First run on a new machine

Needs Docker Desktop, Node 20+, Python 3.12, `uv`, `make` (`winget install ezwinports.make`) and `gitleaks` (`winget install Gitleaks.Gitleaks`).

```
make install          # uv sync + npm install (root and apps/web)
make env              # starts Supabase, writes .env and apps/web/.env.local
git config core.hooksPath .githooks
make dev              # Supabase, then API/worker/scheduler/Redis containers, then the web dev server
```

| What | Where |
| --- | --- |
| Web | http://localhost:3000 |
| API health | http://localhost:8000/healthz |
| API docs (local only) | http://localhost:8000/docs |
| Supabase Studio | http://127.0.0.1:54323 |
| Mail (Mailpit) | http://127.0.0.1:54324 |
| Postgres | `make psql` |

## Start and stop

- `make dev` starts everything. `make up` restarts only the backend containers.
- `make stop` stops the containers and Supabase. Data is kept in Docker volumes.
- `make logs` follows the API, worker and scheduler logs. Every log line is JSON with a `request_id`.

## Database

- New migration: `npx supabase migration new <name>`. For a table holding customer data, start from `supabase/templates/tenant_table.sql` (`make migration-tenant name=<table>`).
- Apply new migrations locally: `make migrate`.
- Rebuild the local database from scratch: `make db-reset` (LOCAL ONLY; the Claude Code hook blocks any reset without `--local`).
- After a reset, `make db-roles` sets the `app_api` / `app_system` passwords again (`make db-reset` does this for you).
- Never edit a committed migration. Write a new one.

## Tenants, logins and isolation (module 1)

- Two DB login roles: `app_api` (user requests, RLS applies) and `app_system` (worker and admin only). See `docs/decisions/0001-db-access.md`.
- Test data: `make seed-test` creates Agency A (owner, member), Agency B (owner) and a platform admin with TOTP, and writes `.env.test.local` (tokens last 15 minutes).
- Isolation checks: `make test-isolation`, or the full terminal tests with `bash scripts/rls_terminal_tests.sh` (or the `rls-test` skill).
- New tenant table: `make migration-tenant name=<table>`, then add a factory in `tests/isolation/factories.py`; the suite fails until you do.
- First platform admin: `supabase/snippets/create_platform_admin.sql` (SQL only, never a screen). The admin then enrols an authenticator at `/admin/mfa`; admin routes need aal2.
- Someone locked out of a company: check `memberships` and the company's `status` (members of suspended companies see nothing).
- "A company must keep at least one owner": promote another member to owner first.
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
