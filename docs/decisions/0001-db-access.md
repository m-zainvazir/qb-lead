# 0001 · How the backend talks to Postgres so row-level security applies

- Status: accepted
- Date: 2026-11-13
- Module: 0 (needed by module 1)

## Context

Customer data is isolated with Postgres row-level security (RLS) keyed on `tenant_id`. The FastAPI backend and the Celery worker both need the database. If the backend connects as a role that bypasses RLS, every isolation guarantee depends on hand-written `where tenant_id = ...` clauses, and one missed clause leaks data. We want the database to enforce the wall even when the backend has a bug.

Options considered:

1. **Supabase REST (supabase-py) with the user's token.** RLS applies because PostgREST runs as `authenticated`. Every query is an HTTP call, there are no multi-statement transactions, and anything complex (pgvector matching, reporting) needs RPC functions.
2. **Direct Postgres with per-transaction identity.** The backend connects with its own login role, and every request transaction switches to `authenticated` and carries the verified JWT claims. RLS policies see exactly what they would see through PostgREST.
3. **Direct Postgres as the owner or service role, filtering in code.** Rejected: isolation depends on every query being correct.

## Decision

Option 2. Two login roles, two pools, one module that creates them (`packages/core/core/db.py`).

| Path | Login role | Acts as | RLS | Who may use it |
| --- | --- | --- | --- | --- |
| `user_db(claims)` | `app_api` | `authenticated` | applies | everything handling a user request |
| `system_db()` | `app_system` | `service_role` | bypassed | `apps/worker`, `apps/api/api/admin` only |

Details:

- Both login roles are `NOINHERIT`, and their memberships are granted `WITH INHERIT FALSE, SET TRUE`. A bare connection therefore holds **no** table privileges. `app_api` can become only `authenticated`; it cannot `SET ROLE service_role` or `postgres` (checked on 2026-11-13).
- `user_db(claims)` opens a transaction, then runs `SET LOCAL ROLE authenticated` and `select set_config('request.jwt.claims', <claims json>, true)`. Both reset when the transaction ends, so a pooled connection never leaks one user's identity to the next request. `auth.uid()` and `auth.jwt()` work inside policies exactly as they do over PostgREST.
- The claims come only from a JWT the API has verified itself (signature through JWKS, expiry, audience, issuer). The client never supplies claims directly.
- `system_db()` opens a transaction with `SET LOCAL ROLE service_role`.
- Passwords are not in migrations. `python -m api.cli db-roles` sets them from `APP_DB_PASSWORD` and `SYSTEM_DB_PASSWORD`. Each environment has its own values in the host's secret store.
- The import rule (ruff `TID251` in `pyproject.toml`, plus a test) keeps `system_db` out of everything except the worker and the admin module.
- The Supabase REST API stays switched on for the same tables, so RLS policies must also be safe for direct REST calls made with a user's token. The isolation suite tests both paths.

## Consequences

- Real transactions, plain SQL and pgvector are available to the API and the worker through one access layer.
- Every request costs two extra statements (`SET LOCAL ROLE` and `set_config`). This is negligible next to the query itself.
- On hosted Supabase, the connection pooler needs `app_api.<project-ref>` style user names and transaction mode. `SET LOCAL` is transaction-scoped, so it is safe in transaction pooling. Check this when staging is set up.
- `ALTER ROLE ... PASSWORD` may appear in the server's statement log if `log_statement` is `all` or `ddl`. On staging and production, set the passwords from a session with logging off, or rotate them through the Supabase dashboard.
