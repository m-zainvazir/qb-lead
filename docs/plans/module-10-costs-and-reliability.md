# 10 · Costs, monitoring and reliability

## Goal

Spending cannot surprise you, failures reach you within minutes, and the data can be restored. The cost recording started in module 3; this module adds the caps, alerts, backups and drills around it.

## What gets built

- Cost ledger: daily roll-ups of `usage_events` by provider, source, tenant and model.
- `budgets`: a monthly cap and an alert level for the whole platform, each provider, each source and each tenant.
- Enforcement inside `metered_call()`: a warning at 80 percent and a refusal at 100 percent, checked before the call is made.
- Alerts to your own Slack: cap reached, a source failing three runs in a row, queue backlog, error spike, eval score drop, no new leads for a set number of hours.
- Sentry in the web app, API and worker, tagged with release and tenant id, with personal data off.
- Langfuse on its hosted plan for every model call.
- Health routes: `/healthz` (the process is alive) and `/readyz` (database, Redis and providers reachable), plus an outside uptime monitor.
- `failed_jobs`: where failed tasks land, with a retry button in the admin panel.
- Backups: Supabase's own backups plus a weekly encrypted dump kept somewhere else.
- Retention jobs: raw items after 90 days, traces after a set period, full purge of deleted tenants.
- Rate limits backed by Redis: global, per tenant, and stricter on sign-in, ingest and proposal routes.
- Runbooks: source down, provider down, cap reached, restore, rotate a key, suspected breach.

## Build steps

1. Build the roll-up job, the budgets table and the enforcement in `metered_call()`.
2. Add Sentry with release tagging.
3. Add the alert rules, each naming its runbook.
4. Build `failed_jobs` and the retry action.
5. Set up backups, then restore one into a scratch database.
6. Build the retention jobs.
7. Add the rate limits.
8. Run a load test with k6 and record the baseline.
9. Run three failure drills: stop Redis, block the model provider, break a source.
10. Write down the recovery targets, for example restore within 4 hours and lose at most 24 hours of data.

## System design checks

- Caps act before the money is spent, not after the bill.
- When a cap pauses a stage, items wait in their current status and continue when the cap resets or is raised.
- Alerts are deduplicated: one problem, one message.
- Per-tenant sub-caps stop one customer from using up a shared budget.
- Worker concurrency is sized to the server's memory, and the scheduler runs exactly once.
- Every alert links to a runbook that a tired person can follow.

## Security checks

- Sentry and Langfuse receive no secrets, tokens or personal contact details.
- Backups are encrypted, stored off the main server, and readable by as few accounts as possible.
- Rotating one provider key and the login signing secret has been practised.
- Queue dashboards and metrics routes are not public.
- The server has automatic security updates, key-only SSH, a firewall and a ban on repeated failed logins.
- The deploy dashboard is behind a login and, where possible, an IP limit.
- Dependency and image scans run in CI every week.
- A one-page breach note exists: rotate keys, end sessions, find the scope, tell affected customers.

## Other checks

- Budget: actual monthly spend by line item against the 150 dollar target.
- Duties: personal data on leads from the UK and EU brings notification duties after a breach. Ask a lawyer what applies to you.
- Privacy policy: the retention periods in the product match the ones written in the policy.

## Manual tests

1. Set the platform cap just above current spend and run a source. A Slack warning arrives at 80 percent, the run stops at 100 percent, and the admin panel shows capped.
2. Raise the cap. Waiting items continue.
3. Trigger a test error from a hidden admin button. It appears in Sentry within a minute with the release and tenant tag.
4. Stop Redis for a minute. The app shows a clear degraded message. After restart, jobs continue with no duplicates.
5. Break a source's key. After three failed runs you get one Slack alert, not three.
6. Open failed jobs and retry one. It succeeds.
7. Restore last night's backup into a scratch project and sign in there.
8. Check the uptime monitor by stopping the API on staging. You are told within a few minutes.

## Terminal tests

```
# Sign-in guessing: expect 429 before 20 attempts
for i in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST "$SUPA/auth/v1/token?grant_type=password" -H "apikey: $ANON" -H "Content-Type: application/json" \
  -d '{"email":"owner@a.test","password":"wrong"}'; done | sort | uniq -c

# Internal dashboards from outside: expect closed, filtered or 401
nmap -Pn -p 5432,5555,6379,8000,9000 staging.example.com
curl -s -o /dev/null -w "%{http_code}\n" https://staging.example.com:5555/

# Error pages reveal nothing: expect a short generic message, no stack trace or SQL
curl -s "$API/leads/not-a-uuid" -H "Authorization: Bearer $JWT_A"

# Secrets in logs: expect clean
docker compose logs --since 24h | grep -iE "sk-[a-z0-9]{20,}|service_role|password=|authorization: bearer" \
  && echo FOUND || echo clean

# Restore drill: expect the same row counts as the source
pg_restore --dbname "$SCRATCH_DB_URL" --clean latest.dump
psql "$SCRATCH_DB_URL" -c "select count(*) from tenants;"

# The backup file is encrypted: expect it not to be readable as a plain dump
file latest.dump.enc

# Load: 50 users for 2 minutes: expect 95 percent of requests under 500 ms and no errors
k6 run --vus 50 --duration 2m tests/load/inbox.js

# Caps refuse before spending: expect all pass
pytest apps/worker/tests/test_metered_call_caps.py -q

# One tenant cannot drain the shared budget: expect the tenant capped, others still running
python -m worker.cli simulate-spend --tenant $TENANT_B --usd 50

# Per-tenant rate limit: expect 429 for Agency A while Agency B still gets 200
for i in $(seq 1 300); do curl -s -o /dev/null "$API/leads" -H "Authorization: Bearer $JWT_A"; done
curl -s -o /dev/null -w "%{http_code}\n" "$API/leads" -H "Authorization: Bearer $JWT_B"

# Encryption in transit on production: expect no weak protocols or ciphers
docker run --rm drwetter/testssl.sh --quiet https://app.example.com
```

## Tools

Plugins and MCP: Sentry, `supabase`. Skills: Trail of Bits `supply-chain-risk-auditor`. Command line: k6, trivy, testssl. Services: Langfuse, an uptime monitor.

## Done when

- [ ] A cap stops spending before the call, and work continues when it is lifted
- [ ] Errors, failing sources and backlogs alert you within minutes, once each
- [ ] A backup has been restored successfully
- [ ] Monthly spend by line item is visible and under target
- [ ] Phase 2 gate: two agencies fully walled off, and every lead decision explainable from the admin panel
