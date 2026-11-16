# Build status

Updated by Claude Code on every run of the build loop. Newest first inside each section.
Last update: 2026-11-16.

## Where things stand

| Module | State | Notes |
| --- | --- | --- |
| 0 Foundation | Done; database now on hosted **staging** | Since 2026-11-16 there is no local Supabase: the database, login and storage are the staging project (ADR 0004). Deploying the API/web, branch protection and the first CI run are still deferred |
| 1 Tenants, logins and isolation | Done, except your browser checks | All 11 terminal tests pass; security review fixed (`docs/reviews/2026-11-13-module-01.md`) |
| 2 Catalogue and onboarding | Done, except your browser checks and the search-term review | All terminal tests pass; "Done when" ticked with evidence |
| 3 Sources and ingestion | **Done**, except web search (needs a key) and your browser checks | All terminal tests pass; "Done when" ticked with evidence |
| 4–12 | Not started | Built in order |

## What to expect at this phase (end of module 3, finished 2026-11-14)

This is the "collection" half of the product. It is not yet a lead tool: nothing is scored, matched or shown as a lead until modules 4–6.

**Works now (try it):**
- **Accounts and companies.** Sign up (the confirmation email now comes from hosted Supabase to the real address you sign up with), create a company, invite teammates, change roles, switch companies, reset your password. Every company's data is walled off from every other company.
- **Platform admin.** After enrolling an authenticator at `/admin/mfa`, an admin sees all companies, opens one (logged in the audit log), and edits the shared catalogue (`/admin/catalogue`).
- **Onboarding and profile.** A 6-step questionnaire (resumes where you left off) turns your answers into a profile. Within about 30 seconds the profile page shows "Here is what we will look for": your services, the phrases we search, markets, kinds of posts, exclusions, and which example posts would reach you or be skipped, with the reason.
- **Portfolio.** Upload a PDF, Word or text case study; a summary appears after a few seconds. Fake or oversized files are refused.
- **Collection.** Every 30 minutes the worker searches Hacker News (including the monthly hiring and freelancer threads) with the combined phrases of all companies and stores the raw posts. A second run only adds new posts. Every outside call is counted in `usage_events`, and a source stops cleanly at its monthly cap.
- **Your own leads in.** On the company's Inbound page: create a webhook address (shown once) for website forms or n8n, or an email address for forwarded job alerts (Upwork alerts are parsed into title, budget and link). Items stay private to your company and always show as plain text. Links inside them are fetched only through a guard that refuses internal addresses.
- **Admin sources page** (`/admin/sources`): every source with its risk level, spend vs cap, projected monthly cost and share of new items; Run now, switch on or off, set a cap; recent runs and raw items.

**Not there yet (by design):**
- No lead inbox, scores, alerts or proposals: modules 4–7.
- Raw posts are broad on purpose; module 4 decides which are real leads.
- Web search (Exa, Tavily, Serper) is built but off until you add a key.
- Inbound email works locally with a signed test (`scripts/send_test_email.py`); real emails need a Mailgun inbound route and domain (question 5).
- No billing or production yet. The database is the hosted staging project; the API, worker and web still run on your machine.

**How to start it:** `make dev` (containers, then the web dev server), and open http://localhost:3000. Invitation emails land in the local test inbox at http://127.0.0.1:54324.

## Practical tests for you, in order

0. **Staging setup checks (once):** in the Supabase dashboard, confirm the auth settings listed under "Staging (hosted Supabase)" in "Open for you", and paste our two email templates.

1. **Module 1 (accounts):** manual tests 1–8 in `docs/plans/module-01-tenants-and-isolation.md`.
2. **Module 2 (onboarding):** manual tests 1–7 in `docs/plans/module-02-catalogue-and-onboarding.md`, then review the search phrases on the Profile page.
3. **Module 3 (sources):** manual tests 1–7 in `docs/plans/module-03-sources-and-ingestion.md`, using `/admin/sources` (as platform admin after `/admin/mfa`) and your company's Inbound page. For test 4 without Mailgun, run `uv run python scripts/send_test_email.py <your inbound address> --upwork`. Then open the Inbound page after the terminal test's `<script>` item and check that it shows as text with no pop-up.
4. **Automatic checks (no browser):** `make seed-test`, then `bash scripts/rls_terminal_tests.sh`, `bash scripts/m2_terminal_tests.sh` and `bash scripts/m3_terminal_tests.sh` (the last one waits 61 seconds after the flood test). Every line should match the "expect" above it.
5. **Security scans** (stopped earlier for low memory): `make audit`, and the semgrep command in "Open for you" below.

## Module 3 task list

- [x] M3-1 Tables: `sources`, `tenant_sources`, `source_runs`, `raw_items` (pooled or private), `inbound_endpoints`, `fetch_guard_events`; `usage_events` gains run, source and `ts`; `metered_call()` refuses past a monthly cap
- [x] M3-2 Connector interface and a fake connector reading saved sample data (tests)
- [x] M3-3 Hacker News connector (Algolia search, plus the monthly "Who is hiring" and freelancer threads)
- [x] M3-4 Inbound webhook: per-tenant secret (shown once, rotatable), size limit, schema, rate limit per secret
- [x] M3-5 Inbound email (Mailgun signature check), HTML to text, attachments dropped, Upwork alert parser and a general parser
- [x] M3-6 Guarded fetcher for links from outside content, with a blocked-attempts log and `fetch-guard-report`
- [x] M3-7 Web search connector (Exa / Tavily / Serper behind one interface, off until a key exists) and the query planner (code and parsing tests; not run live: no keys)
- [x] M3-8 Scheduler from `sources`, run locks, retries with backoff, failure and cap recording; `run-source` command
- [x] M3-9 Temporary sources page (admin) and an inbound page per company (webhook "Send test", private items as plain text)
- [x] M3-10 `docs/sources.md` register, `connector-new` skill, terminal tests, Done-when

## Module 2 task list (in place of a plan-mode approval, since the loop runs unattended)

- [x] M2-1 Catalogue migrations (`services`, `problems`, `technologies`, links, `markets`, `signal_types`, `onboarding_questions`) and seed data: AI automation, voice agents, web development
- [x] M2-2 Tenant tables from the module 1 template: `tenant_profiles` (versioned), `tenant_services`, `tenant_markets`, `tenant_signals`, `tenant_exclusions`, `portfolio_items`, `profile_compilations`, `service_fingerprints`, `onboarding_progress`; isolation factories
- [x] M2-3 Questionnaire as data; API to read questions, save answers and resume; wizard rendered from data
- [x] M2-4 Profile compiler as an idempotent worker job (search terms per source, versioned)
- [x] M2-5 Embeddings behind an interface (model name and size stored with every vector); `re-embed` command; ADR 0002; minimal `metered_call()` that records cost
- [x] M2-6 Portfolio upload: private bucket, tenant folders, storage policies, size cap, content-type sniffing, extraction in the worker with limits, signed short-lived links
- [x] M2-7 Preview screen ("here is what we will look for") from a fixed set of sample posts
- [x] M2-8 Admin: add a service, market, signal or question as data (API and screen)
- [x] Terminal tests, `rls-test`, Done-when list

## Staging move (2026-11-15/16)

- [x] Hosted project created by you (US East, Free, Postgres 17); `.env` filled
- [x] All 14 migrations pushed unchanged (`make push-staging`); app login passwords set (`make db-roles`)
- [x] `app_api`, `app_system` and admin logins work through the session pooler; row-level security on every table; session check installed
- [x] Local Supabase and Postgres removed: 8 containers, 2 data volumes, the network, 8 images, the semgrep image, 15 GB build cache, `~/.supabase`, `supabase/.temp`, `supabase/.branches`
- [x] Rewired: Makefile, Docker compose (+ standalone Mailpit), `core.targets` safety check, `scripts/psql.py`, `make push-staging`, terminal test scripts, seed-test, isolation suite, docs, ADR 0004
- [x] Terminal tests against staging, raw output shown in the session (2026-11-16):
  - Module 1: tests 1–10 all as expected; isolation suite 324 passed, 10 skipped, 1 error: one test lost its connection to staging mid-run (a network drop, not a wrong answer). Re-run alone: 6 of 6 passed. The suite now takes about 15 minutes, because every query crosses the internet.
  - Module 2: every check as expected (permission error, `[]` twice, 400, 400, policy error 403, 413, 415, 422).
  - Module 3: every check as expected: 404, 413, flood 60 × 202 and 140 × 429, both internal links blocked and logged, `[]`, `[]`, 401; Hacker News ran 30 phrases twice and the second run added nothing; every call recorded in `usage_events`.
  - Database tests: 13 passed (12 before, plus the regression test below). Unit tests: 162 passed.
- [x] **Bug found and fixed (module 3):** a collection run with no search phrases (before any company has finished onboarding) moved the "search since" time forward, so later runs skipped older posts for good. Only runs that really searched move it now; regression test `test_a_run_without_queries_does_not_move_the_search_window`. On staging the very first Hacker News run hit this before the fix, so staging only collects posts from 2026-11-16 09:46 onwards (test data; nothing to repair).
- [x] Test changes for staging: the flood test sends its 200 requests 20 at a time (sent one by one, each waits on the hosted database and fewer than 60 land in a minute); module 3 tests first complete Agency A's onboarding through the API (`scripts/onboard_test_company.py`) so collection has phrases to search.

## Questions for you

1. **Embeddings provider.** No API key is configured, so I used a local, free model (fastembed `BAAI/bge-small-en-v1.5`, 384 dimensions) behind an interface (`docs/decisions/0002-embeddings.md`). Do you want OpenAI (`text-embedding-3-small`), Voyage or another provider later? Switching is a setting plus `python -m worker.cli re-embed`.
2. **Git identity.** Commits use "Muhammad Zain" and your work email (repo-local setting). Change it if needed.
3. **GitHub remote and app host.** The staging *database* exists now. Still needed for CI and deploying the API/worker/web: the repo URL and a host (Railway or Hetzner + Coolify) when ready.
4. **Paid sources and keys.** Hacker News, the webhook and email need no key and are live. Web search is ready for Exa, Tavily or Serper: which one, and with what monthly cap? (The defaults are $20, $20 and $10, set in `/admin/sources`.) Later sources (X, Apify, job boards) need your go-ahead. LinkedIn is red-risk (its terms forbid automated access) and will not be built without a written decision.
5. **Inbound email provider.** I chose Mailgun inbound routes because Mailgun signs each delivery (HMAC). Postmark and SendGrid inbound do not sign (only basic auth). Is Mailgun fine, and which domain should receive mail (for example `in.yourdomain.com`)?

## Open for you (tests and manual steps)

### Staging (hosted Supabase)
- [ ] `.env`: change `APP_ENV=local` to `APP_ENV=staging`.
- [ ] `apps/web/.env.local`: set `SUPABASE_URL` and `SUPABASE_ANON_KEY` to the same values as in `.env` (it still points at the deleted local stack, so the web app cannot sign in until this is done).
- [ ] Dashboard, Authentication: Site URL `http://localhost:3000`, redirect URL `http://localhost:3000/**`; confirm email on; minimum password length 10 with lowercase, uppercase and digits; access token expiry 900 seconds; TOTP MFA on.
- [ ] Dashboard, Authentication, Email templates: paste `supabase/templates/email/confirmation.html` into "Confirm signup" and `recovery.html` into "Reset password" (our sign-in pages expect their links).
- [ ] Before anyone but you signs up: a real email sender (the built-in one sends only a few emails an hour), and add a second owner to the Supabase organization.
- [ ] The Free plan pauses after about a week without use: resume it in the dashboard if requests start failing.

### Module 2
- [ ] Manual tests 1–7 in a browser (`docs/plans/module-02-catalogue-and-onboarding.md`). Pages: `/t/<company>/onboarding`, `/profile`, `/portfolio`, and `/admin/catalogue` (admin, after `/admin/mfa`).
- [ ] Build step 8: read the generated search terms for the first five real profiles and tell me what to change. They are on the Profile page under "Phrases we search for", and in `profile_compilations.search_terms`.
- [ ] The first embedding run downloads the model (about 130 MB) into the `models` Docker volume.

### Module 1
- [ ] Manual tests 1–8 in a browser (`docs/plans/module-01-tenants-and-isolation.md`). Sign-up and reset emails now come from hosted Supabase to real inboxes; invitations land in http://127.0.0.1:54324. Start with `make dev`.
- [ ] The first platform admin on a real environment: enrol an authenticator at `/admin/mfa` first, then run `supabase/snippets/create_platform_admin.sql` (it refuses users without a verified authenticator).
- [ ] Note: a page for another company shows "Not found" but with HTTP status 200, because the page streams. No data from the other company is in the response.

### Module 0
- [ ] Install the plugins listed in `docs/plans/00-overview.md` with `/plugin install …`
- [ ] Open a new terminal so `make` and `gitleaks` (installed with winget) are on PATH
- [ ] Clone into a fresh folder, fill the two env files (`docs/runbook.md`), run `make install && make dev`, and check it works in under 30 minutes
- [ ] Add a GitHub remote, push, and check the CI run (the `database` job runs the isolation suite)

## Decisions made without you (easy to change)

- 2026-11-16: Kept the repo's `supabase/` folder and the Supabase CLI (a dev dependency) after removing local Supabase: they are how migrations reach staging. Kept `make` and `gitleaks` (still used).
- 2026-11-16: Connections use the session pooler (port 5432), not the transaction pooler, so `db.py` needed no change (ADR 0004).
- 2026-11-16: `make push-staging` is the only way migrations reach a hosted project; it accepts only refs in `.claude/staging-targets.txt`.

- 2026-11-14: Public inbound routes reach the database through a new narrow role, `ingest`, that can only call `private.ingest_*` functions (ADR 0003), rather than through `system_db()`.
- 2026-11-14: Webhook limit is 60 requests per minute per address (`WEBHOOK_RATE_PER_MINUTE`).
- 2026-11-14: Links to upwork.com, linkedin.com, facebook.com, instagram.com and x.com are kept but never fetched (site terms).
- 2026-11-14: Raw payloads are kept for 90 days (`raw_items.expires_at`). The deletion job comes with module 10's reliability work.
- 2026-11-14: Preview threshold: a sample post "would reach you" at cosine similarity ≥ 0.70 with one of your service fingerprints (tuned on the seeded samples). The constant `PREVIEW_MATCH` is in `apps/worker/worker/compiler.py`.
- 2026-11-14: Portfolio summaries are a plain extract (the first sentences). An AI summary can replace it in module 7.
- 2026-11-14: `metered_call()` and the `usage_events` table were built in module 2 rather than module 3, because embedding costs had to be recorded now.
- 2026-11-14: Module 2's terminal tests call the API without `X-Tenant-Id`. The API now uses your company when you belong to exactly one, and still requires the header otherwise.
- 2026-11-14: Embeddings default to a local model (see question 1).
- 2026-11-13: Company pages live under `/t/<companyId>/…`; switching company goes through `/switch/<id>`.
- 2026-11-13: The DB access design is in `docs/decisions/0001-db-access.md`.

## Known gaps carried forward

- Audit entries record the web server's IP, not the user's (review finding 9). Fix with the deploy work.
- Invitation clean-up (purge old ones after 30 days) and the audit log retention period are listed in `docs/privacy.md`.
- Scanned (image-only) PDFs give "no text found"; OCR is not included.
