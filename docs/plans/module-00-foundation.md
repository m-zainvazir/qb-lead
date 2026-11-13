# 0 · Foundation and developer setup

## Goal

One command starts the whole stack on your machine, every push runs tests and scans, and Claude Code has its rules, hooks and tools. Nothing customer-facing exists yet.

## What gets built

- A single repo: `apps/web` (Next.js), `apps/api` (FastAPI), `apps/worker` (Celery), `supabase/` (migrations and seed data), `evals/` (labelled test sets), `infra/` (Docker and deploy files), `docs/` (these plans, runbook, decisions, source register).
- Three environments: local (Supabase CLI stack plus Docker Compose), staging and production. Staging and production use separate Supabase projects.
- Docker Compose services: API, worker, scheduler (Celery beat) and Redis.
- Continuous integration on GitHub Actions: lint, type checks, unit tests, gitleaks, semgrep, `pip-audit`, `npm audit`.
- `.env.example` with variable names only. Real values live in the host's secret store.
- `/healthz` endpoint that returns status and the git commit, and JSON logs with a request id.
- Small command-line helpers, `python -m api.cli` and `python -m worker.cli`. Later modules add test commands to them.
- `CLAUDE.md`, hooks, plugins, MCP servers and empty versions of the five custom skills from the Toolbox.

## Build steps

1. Create the repo and folders. Write `CLAUDE.md` with the rules from the Toolbox.
2. Run `supabase init` and `supabase start`. Commit an empty first migration.
3. Build the FastAPI skeleton: settings read from the environment, fail at startup when one is missing, `/healthz`, JSON logging.
4. Add the Celery worker and scheduler with one heartbeat task.
5. Add the Next.js skeleton with a placeholder sign-in page.
6. Write Docker Compose and a `make dev` target that starts everything.
7. Add the CI pipeline and protect the main branch.
8. Install the plugins, MCP servers and hooks.
9. Deploy to staging (Hetzner with Coolify, or Railway) to prove the path from push to live.
10. Write the first decision record: how the backend will talk to Postgres so that row-level security applies (module 1 depends on it).

## System design checks

- A fresh clone is running in under 30 minutes with one command.
- The API and the worker share one settings module and one database access layer.
- Staging and production differ only in configuration, never in code.
- The scheduler runs as exactly one process, so jobs are not triggered twice.
- Each service can restart on its own without the others failing.

## Security checks

- `.env` is ignored by git and gitleaks is clean across the full history.
- Each environment has its own keys. Production keys never sit on the laptop.
- CI must pass before a merge to main.
- Containers run as a non-root user.
- The server exposes only web ports. SSH uses keys only, a firewall is on, and security updates install automatically.
- Redis has a password and is not reachable from the internet.
- Automatic dependency update pull requests are switched on.

## Other checks

- Cost: the fixed monthly bill (server and Supabase plan) is written down and fits the budget.
- Runbook: `docs/runbook.md` covers start, stop, deploy and roll back.
- Backups: production database backups are enabled before any real data arrives.

## Manual tests

1. Clone the repo into a new folder, run `make dev`, open `http://localhost:3000`. The page loads.
2. Open `$API/healthz`. It shows status ok and the current commit.
3. Push a branch with a deliberate lint error. CI fails. Fix it. CI passes.
4. Ask Claude Code to edit `.env`. The hook blocks it.
5. Ask Claude Code to run `supabase db reset` against staging. The hook blocks it.
6. Open the staging address. It loads over HTTPS with a valid certificate.

## Terminal tests

```
# Secrets in code or history: expect no leaks found
gitleaks detect --source . --redact

# Insecure patterns: expect no high-severity findings
semgrep scan --config auto apps/

# Vulnerable packages: expect none at high or critical
pip-audit -r apps/api/requirements.txt
(cd apps/web && npm audit --audit-level=high)

# Open ports on staging: expect only 80 and 443 open (22 if you use SSH from anywhere)
nmap -Pn -p 22,80,443,5432,6379,8000 staging.example.com

# Containers run as non-root: expect a uid other than 0
docker compose exec api id

# Image scan: expect no high or critical issues
trivy image leadgen-api:latest --severity HIGH,CRITICAL

# Redis from outside: expect connection refused or timeout
redis-cli -h staging.example.com -p 6379 ping
```

## Tools

Plugins: `security-guidance`, `context7`, `commit-commands`, `hookify`, `skill-creator`. MCP: GitHub. Command line: gitleaks, semgrep, trivy.

## Done when

- [ ] `make dev` starts web, API, worker, scheduler, Redis and local Supabase. Each part has been started and checked (Supabase, `make up`, `npm run dev`); a one-command run from a fresh clone is still open.
- [ ] CI runs lint, types, tests, gitleaks, semgrep and audits on every push. The workflow is written and every step has been run locally; deferred until a GitHub remote exists.
- [ ] Staging is live over HTTPS with only web ports open. Deferred by decision (local only for now).
- [x] Hooks block edits to `.env` and destructive database commands (`.claude/settings.json`, `scripts/hooks/`, tests in `scripts/hooks/test_hooks.py`)
- [x] `CLAUDE.md`, the runbook and the first decision record are committed (`docs/decisions/0001-db-access.md`)
