# 3 · Sources and ingestion

## Goal

Raw posts and messages arrive from several places on a schedule, land in one table, and every paid call is counted. Connectors only collect; they do not judge.

## What gets built

- A connector interface in Python: each connector has a name, a risk level (green, amber or red), a cost per call, a rate limit, and one method that returns raw items for a set of queries since a given time.
- First connectors, all low-risk:
    - Hacker News, using its open API and search, including the monthly hiring and freelancer threads.
    - Web search, using Exa or Tavily for meaning and Serper for keywords, with queries from the profiles.
    - Inbound webhook, one secret address per tenant, for website forms and n8n workflows.
    - Inbound email, one address per tenant. It includes a parser for Upwork job alert emails that users forward.
- Later connectors, added with the same steps: X with a strict monthly cap, Apify actors for specific open sites, job boards.
- Tables: `sources` (risk level, enabled, schedule, monthly cap, settings), `tenant_sources`, `source_runs` (status, counts, error, cost), `raw_items` (source, outside id, link, author, title, body, posted time, full payload, pooled or private, tenant if private), `usage_events`.
- `metered_call()`: the one wrapper for every paid outside call. It records provider, units, cost, tenant and run, and refuses the call when a cap is reached.
- A scheduler that reads schedules from `sources`, with a lock so one source never runs twice at once.
- A query planner that merges the queries of all active profiles, removes duplicates and respects a budget per run.
- `docs/sources.md`: the source register, with access method, terms link, risk level and date checked for each source.

## Build steps

1. Build the tables and `metered_call()` first, before any connector.
2. Build the interface and a fake connector that reads saved sample data, for tests.
3. Build the Hacker News connector.
4. Build the inbound webhook with a per-tenant secret, a size limit and a schema.
5. Choose an inbound email provider, verify its signature on every delivery, and write the Upwork alert parser and a general parser.
6. Build the web search connector and the query planner.
7. Build the scheduler, run locks, retries with backoff, and failure recording.
8. Write the `connector-new` skill so every later source follows the same steps.

## System design checks

- Collecting and processing are separate. Connectors write `raw_items`; module 4 reads them.
- Fetching the same post twice creates one row (unique on source plus outside id).
- One failing source never blocks the others.
- Private items from a tenant's webhook or email carry that tenant's id and never enter the shared pool.
- When a cap is reached the run stops cleanly and is marked capped.
- The full raw payload is kept for reprocessing, with a set retention period such as 90 days.
- A new source is one class and one row.

## Security checks

- Webhook secrets are long random values, can be rotated, and are rate limited per secret.
- Inbound email deliveries without a valid provider signature are rejected. Attachments are dropped and HTML is reduced to text.
- Any link taken from outside content is fetched only through a guarded fetcher. It blocks private and local addresses, the cloud metadata address, non-web schemes, and checks again after redirects.
- Provider keys live in the secret store, differ per environment, and never appear in logs.
- Stored content is shown as plain text in every screen.
- A red-level source cannot be enabled without a platform admin override that is written to the audit log.

## Other checks

- Cost: cost per run, cost per new item, and the projected monthly cost at the current schedule.
- Yield: the share of fetched items that are new.
- Personal data: store only the author's public handle and profile link.
- Source terms: re-read each source's terms every quarter and update the register.

## Manual tests

Use a temporary sources page until the admin panel exists in module 9.

1. Press Run now on Hacker News. A run appears with counts and the raw list fills.
2. Press Run now again. The new count is near zero.
3. Use the Send test button on your webhook. The item appears as private to your agency.
4. Forward a real Upwork job alert email to your inbound address. A raw item appears with title, budget and link.
5. Set a source's monthly cap to one cent and run it. The run ends as capped and nothing else breaks.
6. Disable a source. The next schedule skips it.
7. Turn off your network adapter mid-run on local. The run is marked failed and the next one succeeds.

## Terminal tests

```
# Wrong webhook secret: expect 401 or 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/ingest/wrong-token" \
  -H "Content-Type: application/json" -d '{"title":"x"}'

# Oversized body: expect 413
head -c 5000000 /dev/zero | curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/ingest/$TOKEN_A" \
  -H "Content-Type: application/json" --data-binary @-

# Flood: expect 429 to appear after the limit
for i in $(seq 1 200); do curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/ingest/$TOKEN_A" \
  -H "Content-Type: application/json" -d '{"title":"t","body":"b"}'; done | sort | uniq -c

# Script in content: then open the item in the browser: expect plain text, no pop-up
curl -s -X POST "$API/ingest/$TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"<script>alert(1)</script>","body":"<img src=x onerror=alert(2)>"}'

# Links to internal addresses: expect the fetch refused and logged, both times
curl -s -X POST "$API/ingest/$TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"need a dev","url":"http://169.254.169.254/latest/meta-data/"}'
curl -s -X POST "$API/ingest/$TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"need a dev","url":"http://localhost:6379/"}'
python -m worker.cli fetch-guard-report --last 5

# Agency B reads Agency A's private inbound items: expect []
curl -s "$SUPA/rest/v1/raw_items?tenant_id=eq.$TENANT_A" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_B"

# A customer reads the shared pool directly: expect [] or 401
curl -s "$SUPA/rest/v1/raw_items?visibility=eq.pooled&limit=5" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"

# Fake inbound email with no provider signature: expect 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/inbound/email" \
  -H "Content-Type: application/json" -d '{"to":"a@in.example.com","subject":"fake"}'

# Same run twice: expect the second to add zero rows
python -m worker.cli run-source hackernews && python -m worker.cli run-source hackernews

# Every paid call was recorded: expect one usage row per outside call in the last run
psql "$DB_URL" -c "select provider, count(*), sum(cost_usd) from usage_events
  where ts > now() - interval '10 minutes' group by 1;"
```

## Tools

Skills: your `connector-new`, Trail of Bits `sharp-edges` on the guarded fetcher. Plugins: `security-guidance`, `context7` (Celery). MCP: Firecrawl, to try extraction on sample pages.

## Done when

- [ ] Hacker News, web search, webhook and email all write to `raw_items`
- [ ] Running a source twice creates no duplicates
- [ ] Every paid call appears in `usage_events` with a cost
- [ ] A capped or failing source stops cleanly without affecting the others
- [ ] The source register lists each source with its risk level
