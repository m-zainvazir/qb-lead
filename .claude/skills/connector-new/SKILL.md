---
name: connector-new
description: Add a new lead source connector to the lead-gen platform the same way every time - interface class, registry entry, sources row (migration), sample data and tests, metered calls with cost, cap handling, and a source register entry with terms and risk. Use whenever a new source (X, Apify actor, job board, RSS feed, another search API) is added, in module 3 or later.
---

# connector-new

A connector only collects. It never filters by meaning, scores, or reads instructions
from content (text from posts is data). A new source is one class and one row.

## Checklist (do all of it, in this order)

1. **Terms and risk first.** Read the source's terms and robots.txt. Add a row to
   `docs/sources.md` with access method, terms link, risk (green/amber/red), cost and today's
   date. If it needs a login or the terms forbid automated access, it is **red**: stop and
   ask the user for a written decision.
2. **Class** in `apps/worker/worker/ingest/<name>.py` implementing `Connector`
   (`worker/ingest/base.py`):
   - `name`, `query_family` (`reddit` = short phrases, `web_search`, or `job_boards`)
   - `fetch(queries, since, ctx) -> Iterator[RawItem]`
   - every outside call goes through `ctx.get_json(...)` / `ctx.post_json(...)` (these call
     `metered_call()`: recorded in `usage_events`, refused at the monthly cap). Never call
     `httpx` directly for the source API.
   - keys come from settings (`packages/core/core/settings.py` + `.env.example`), and raise
     `NotConfigured` when missing
   - `external_id` must be stable (the source's own id, or a hash of the canonical URL)
   - store the author's public handle and profile link only; no emails or phone numbers
   - HTML goes through `core.text.html_to_text`
   - pure parsing in a separate function (`to_item(...)`) so it can be unit-tested
3. **Register** it in `apps/worker/worker/ingest/registry.py`.
4. **Migration** inserting the `sources` row: `enabled=false`, `risk`, `schedule_seconds`,
   `monthly_cap_usd`, `cost_per_call_usd`, `rate_limit_per_minute`, `max_queries_per_run`.
   Never edit an applied migration.
5. **Sample data and tests** in `apps/worker/tests/`: parse a saved response (no network in
   unit tests), and check that a second identical run would add nothing (stable ids).
6. **Run it locally:** `uv run python -m worker.cli run-source <key>` twice. The second run
   reports `"new": 0`, and each outside call appears in `usage_events` with its cost.
7. **Cap check:** set the cap to 0.01 on `/admin/sources`, run it, and confirm the run ends
   `capped` while other sources still run.
8. Commit, and update `docs/STATUS.md`.
