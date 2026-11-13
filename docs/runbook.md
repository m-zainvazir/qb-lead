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

## Debugging

- "Database pools are not open": the API started without its lifespan; check `make logs` for a settings error at startup.
- A missing setting fails startup with a pydantic `ValidationError` that names the variable.
- Scheduler: exactly one `scheduler` container. Never scale it.

## Staging and production

Not set up yet (module 0's staging step is deferred). When it is:

- Add the production project ref and host to `.claude/protected-targets.txt`.
- Turn on leaked-password protection (HIBP) and MFA in the hosted Supabase Auth settings.
- Enable database backups before any real data arrives.
