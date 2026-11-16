# Lead Generation Platform

Multi-tenant platform that finds warm and hot leads for freelancers and agencies. See `CLAUDE.md` for the rules and `docs/plans/` for the module plans.

## Layout

| Path | What |
| --- | --- |
| `apps/web` | Next.js + TypeScript frontend |
| `apps/api` | FastAPI backend (package `api`) |
| `apps/worker` | Celery worker and scheduler (package `worker`) |
| `packages/core` | Shared Python: settings, logging, database access (package `core`) |
| `supabase/` | Migrations, seed data, templates, SQL snippets |
| `tests/` | Cross-app tests (isolation suite) |
| `infra/` | Docker and Compose files |
| `scripts/` | Hooks and helper scripts |
| `docs/` | Plans, runbook, decision records, source register |

## Quick start

Needs Docker, Node 20+, Python 3.12, `uv` and `make`. The database, login and storage are a
hosted Supabase **staging** project; there is no local Supabase. Fill `.env` from
`.env.example` (staging values) and `apps/web/.env.local` (see `docs/runbook.md`).

```
make install
make dev      # API, worker, scheduler, Redis, Mailpit in Docker, then the web dev server
```

Web: http://localhost:3000. API: http://localhost:8000/healthz. Test inbox (Mailpit): http://localhost:54324.

See `docs/runbook.md` for the full start, stop and debug notes.
