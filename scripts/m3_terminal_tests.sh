#!/usr/bin/env bash
# Module 3 terminal tests (docs/plans/module-03-sources-and-ingestion.md), local stack or STAGING (never production).
#
#   make seed-test && bash scripts/m3_terminal_tests.sh
#
# The plan's commands, with local adaptations: `python -m worker.cli` runs through uv
# from the repo root, and `psql` is scripts/psql.py.
set -uo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
source scripts/terminal_env.sh
python() { uv run python "$@"; }

echo "# Wrong webhook secret: expect 401 or 404"
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/ingest/wrong-token" \
  -H "Content-Type: application/json" -d '{"title":"x"}'

echo "# Oversized body: expect 413"
head -c 5000000 /dev/zero | curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/ingest/$TOKEN_A" \
  -H "Content-Type: application/json" --data-binary @-

echo "# Flood: expect 429 to appear after the limit"
for i in $(seq 1 200); do curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/ingest/$TOKEN_A" \
  -H "Content-Type: application/json" -d '{"title":"t","body":"b"}'; done | sort | uniq -c
echo "#   (waiting 61 s for the rate-limit window to reset)"; sleep 61

echo "# Script in content: then open the item in the browser: expect plain text, no pop-up"
curl -s -X POST "$API/ingest/$TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"<script>alert(1)</script>","body":"<img src=x onerror=alert(2)>"}'; echo

echo "# Links to internal addresses: expect the fetch refused and logged, both times"
curl -s -X POST "$API/ingest/$TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"need a dev","url":"http://169.254.169.254/latest/meta-data/"}'; echo
curl -s -X POST "$API/ingest/$TOKEN_A" -H "Content-Type: application/json" \
  -d '{"title":"need a dev","url":"http://localhost:6379/"}'; echo
sleep 5  # the worker fetches in the background
python -m worker.cli fetch-guard-report --last 5

echo "# Agency B reads Agency A's private inbound items: expect []"
curl -s "$SUPA/rest/v1/raw_items?tenant_id=eq.$TENANT_A&select=id,title" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_B"; echo

echo "# A customer reads the shared pool directly: expect [] or 401"
curl -s "$SUPA/rest/v1/raw_items?visibility=eq.pooled&limit=5&select=id,title" -H "apikey: $ANON" -H "Authorization: Bearer $JWT_A"; echo

echo "# Fake inbound email with no provider signature: expect 401"
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API/inbound/email" \
  -H "Content-Type: application/json" -d '{"to":"a@in.example.com","subject":"fake"}'

echo "# Same run twice: expect the second to add zero rows"
python -m worker.cli run-source hackernews && python -m worker.cli run-source hackernews

echo "# Every paid call was recorded: expect one usage row per outside call in the last run"
psql "$DB_URL" -c "select provider, count(*), sum(cost_usd) from usage_events
  where ts > now() - interval '10 minutes' group by 1;"
psql "$DB_URL" -c "select source_key, status, queries, fetched, new_items,
  (select count(*) from usage_events u where u.run_id = r.id) as calls_recorded
  from source_runs r order by started_at desc limit 2;"
