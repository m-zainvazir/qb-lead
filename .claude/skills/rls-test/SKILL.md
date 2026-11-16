---
name: rls-test
description: Run the two-tenant isolation tests (Agency A vs Agency B) against the STAGING project and show the raw output - module 1's terminal tests 1-11 plus the isolation suite that discovers every table with tenant_id. Use when the user asks for rls-test, isolation tests, tenant isolation checks, or before declaring any module that adds a tenant table done.
---

# rls-test

STAGING ONLY (or a local stack, if one ever exists again). Never production: the scripts
refuse any project not listed in `.claude/staging-targets.txt` (core.targets), and so must you.
Everything goes over the internet to the staging project, so the suite takes several minutes.

## Steps

1. Make sure the containers are up: `make up` (`curl -s localhost:8000/healthz`). Apply new migrations with `make push-staging`.
2. Build the web app once if terminal test 9 should run: `cd apps/web && npm run build`.
3. Seed fresh users and tokens (tokens last 15 minutes): `make seed-test`.
4. Run the terminal tests and show the output **raw**, unedited:
   `bash scripts/rls_terminal_tests.sh` (module 1), `bash scripts/m2_terminal_tests.sh` (module 2: catalogue, profiles, storage) and `bash scripts/m3_terminal_tests.sh` (module 3: inbound, guarded fetcher, sources)
5. Compare each result with the expectation printed above it. Report a table:
   test | expected | got | pass/fail. Do not summarise away a failure.

## When a new table is added

- A table with a `tenant_id` column is discovered automatically by `tests/isolation`.
- It fails until it has a factory in `tests/isolation/factories.py`. Add one that inserts
  a valid row for a tenant and returns a complete row a user might try to insert.
- Start new tenant tables from `make migration-tenant name=<table>`.

## What the suite covers

- `test_structure.py`: every public table has RLS enabled and forced, no anon grants, no
  TRUNCATE/TRIGGER/REFERENCES for app roles, no `using (true)` policies; every tenant
  table's policies call `is_member`/`has_role` and `tenant_id` is indexed.
- `test_behaviour.py`: for every tenant table, Agency A cannot read, insert, update or delete
  Agency B's rows, anon reads nothing, and A can see its own rows (positive control).
- `test_rules.py`: role changes, last owner, audit log append-only, invitations single use,
  email-bound and expiring, platform admin needs MFA.
- `test_rest.py`: the same wall through Supabase REST and through our API.
