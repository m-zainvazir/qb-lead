# Build status

Updated by Claude Code on every run of the build loop. Newest first inside each section.
Last update: 2026-11-14.

## Where things stand

| Module | State | Notes |
| --- | --- | --- |
| 0 Foundation (local slice) | Done locally | Staging, branch protection and the first CI run are deferred (no remote yet) |
| 1 Tenants, logins and isolation | Done, except your browser checks | All 11 terminal tests pass; security review fixed (`docs/reviews/2026-11-13-module-01.md`) |
| 2 Catalogue and onboarding | Done, except your browser checks and the search-term review | All terminal tests pass; "Done when" ticked with evidence |
| 3 Sources and ingestion | **In progress** | Key-free sources first; web search waits for a key (question 4) |
| 4Ã¢â‚¬â€œ12 | Not started | Built in order |

## What to expect at this phase (end of module 3)

This is the "collection" half of the product. It is not yet a lead tool: nothing is scored, matched or shown as a lead until modules 4–6.

**Works now (try it):**
- **Accounts and companies.** Sign up (confirmation email at http://127.0.0.1:54324), create a company, invite teammates, change roles, switch companies, reset your password. Every company's data is walled off from every other company.
- **Platform admin.** After enrolling an authenticator at `/admin/mfa`, an admin sees all companies, opens one (logged in the audit log), and edits the shared catalogue (`/admin/catalogue`).
- **Onboarding and profile.** A 6-step questionnaire (resumes where you left off) turns your answers into a profile. Within about 30 seconds the profile page shows "Here is what we will look for": your services, the phrases we search, markets, kinds of posts, exclusions, and which example posts would reach you or be skipped, with the reason.
- **Portfolio.** Upload a PDF, Word or text case study; a summary appears after a few seconds. Fake or oversized files are refused.
- **Collection.** Every 30 minutes the worker searches Hacker News (including the monthly hiring and freelancer threads) with the combined phrases of all companies and stores the raw posts. A second run only adds new posts. Every outside call is counted in `usage_events`, and a source stops cleanly at its monthly cap.

**Not there yet (by design):**
- No lead inbox, scores, alerts or proposals: modules 4–7.
- Raw posts are broad on purpose; module 4 decides which are real leads.
- Web search (Exa, Tavily, Serper) is built but off until you add a key; inbound email needs a provider (question 5).
- No billing, staging or production yet.

**How to start it:** `npx supabase start`, then `make up`, then `cd apps/web && npm run dev`, and open http://localhost:3000.

## Practical tests for you, in order

1. **Module 1 (accounts):** manual tests 1–8 in `docs/plans/module-01-tenants-and-isolation.md`.
2. **Module 2 (onboarding):** manual tests 1–7 in `docs/plans/module-02-catalogue-and-onboarding.md`, then review the search phrases on the Profile page.
3. **Module 3 (sources):** manual tests in `docs/plans/module-03-sources-and-ingestion.md` once the temporary sources page lands (task M3-9). Until then: `uv run python -m worker.cli run-source hackernews` twice; the second run reports `"new": 0`.
4. **Automatic checks (no browser):** `make seed-test`, then `bash scripts/rls_terminal_tests.sh` and `bash scripts/m2_terminal_tests.sh`. Every line should match the "expect" above it.
5. **Security scans** (stopped earlier for low memory): `make audit`, and the semgrep command in "Open for you" below.

## Module 3 task list

- [x] M3-1 Tables: `sources`, `tenant_sources`, `source_runs`, `raw_items` (pooled or private), `inbound_endpoints`, `fetch_guard_events`; `usage_events` gains run, source and `ts`; `metered_call()` refuses past a monthly cap
- [x] M3-2 Connector interface and a fake connector reading saved sample data (tests)
- [x] M3-3 Hacker News connector (Algolia search, plus the monthly "Who is hiring" and freelancer threads)
- [ ] M3-4 Inbound webhook: per-tenant secret (shown once, rotatable), size limit, schema, rate limit per secret
- [ ] M3-5 Inbound email (Mailgun signature check), HTML to text, attachments dropped, Upwork alert parser and a general parser
- [ ] M3-6 Guarded fetcher for links from outside content, with a blocked-attempts log and `fetch-guard-report`
- [x] M3-7 Web search connector (Exa / Tavily / Serper behind one interface, off until a key exists) and the query planner (code and parsing tests; not run live: no keys)
- [x] M3-8 Scheduler from `sources`, run locks, retries with backoff, failure and cap recording; `run-source` command
- [ ] M3-9 Temporary sources page (admin) and an inbound page per company (webhook "Send test", private items as plain text)
- [ ] M3-10 `docs/sources.md` register, `connector-new` skill, terminal tests, Done-when

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

## Questions for you

1. **Embeddings provider.** No API key is configured, so I used a local, free model (fastembed `BAAI/bge-small-en-v1.5`, 384 dimensions) behind an interface (`docs/decisions/0002-embeddings.md`). Do you want OpenAI (`text-embedding-3-small`), Voyage or another provider later? Switching is a setting plus `python -m worker.cli re-embed`.
2. **Git identity.** Commits use "Muhammad Zain" and your work email (repo-local setting). Change it if needed.
3. **GitHub remote and staging host.** Needed for CI and module 0's staging step. Tell me the repo URL and host (Railway or Hetzner + Coolify) when ready.
5. **Inbound email provider.** I chose Mailgun inbound routes because Mailgun signs each delivery (HMAC). Postmark and SendGrid inbound do not sign (only basic auth). Is Mailgun fine, and which domain should receive mail (for example `in.yourdomain.com`)?
4. **Module 3 sources and keys.** Which sources should come first, and which accounts or keys exist? Without keys I will start with sources that need none: Reddit's public JSON listings, Hacker News (Algolia API), RSS feeds, and inbound email/webhook. Paid search (Google CSE, SerpAPI, Firecrawl) and LinkedIn will wait for your go-ahead and keys.

## Open for you (tests and manual steps)

### Module 2
- [ ] Manual tests 1Ã¢â‚¬â€œ7 in a browser (`docs/plans/module-02-catalogue-and-onboarding.md`). Pages: `/t/<company>/onboarding`, `/profile`, `/portfolio`, and `/admin/catalogue` (admin, after `/admin/mfa`).
- [ ] Build step 8: read the generated search terms for the first five real profiles and tell me what to change. They are on the Profile page under "Phrases we search for", and in `profile_compilations.search_terms`.
- [ ] Note: my smoke tests left some catalogue rows switched off (not deleted) in your local database: a "Chatbots (smoke test)" service, the market `NZ`, the signal `smoke_signal` and the question `smoke_question`. Your manual test 7 can still add "Chatbots" with the slug `chatbots`. To use NZ for real, switch it on and rename it in the admin catalogue (or `make db-reset` for a clean local database).
- [ ] The first embedding run downloads the model (about 130 MB) into the `models` Docker volume.

### Module 1
- [ ] Manual tests 1Ã¢â‚¬â€œ8 in a browser (`docs/plans/module-01-tenants-and-isolation.md`). Emails arrive at http://127.0.0.1:54324. Start with `make dev`, or Supabase + `make up` + `cd apps/web && npm run dev`.
- [ ] The first platform admin on a real environment: enrol an authenticator at `/admin/mfa` first, then run `supabase/snippets/create_platform_admin.sql` (it refuses users without a verified authenticator).
- [ ] Note: a page for another company shows "Not found" but with HTTP status 200, because the page streams. No data from the other company is in the response.

### Module 0
- [ ] Install the plugins listed in `docs/plans/00-overview.md` with `/plugin install Ã¢â‚¬Â¦`
- [ ] Open a new terminal so `make` and `gitleaks` (installed with winget) are on PATH
- [ ] Clone into a fresh folder, run `make install && make env && make dev`, and check it works in under 30 minutes
- [ ] Add a GitHub remote, push, and check the CI run (the `database` job runs the isolation suite)

## Decisions made without you (easy to change)

- 2026-11-14: Preview threshold: a sample post "would reach you" at cosine similarity Ã¢â€°Â¥ 0.70 with one of your service fingerprints (tuned on the seeded samples). The constant `PREVIEW_MATCH` is in `apps/worker/worker/compiler.py`.
- 2026-11-14: Portfolio summaries are a plain extract (the first sentences). An AI summary can replace it in module 7.
- 2026-11-14: `metered_call()` and the `usage_events` table were built in module 2 rather than module 3, because embedding costs had to be recorded now.
- 2026-11-14: Module 2's terminal tests call the API without `X-Tenant-Id`. The API now uses your company when you belong to exactly one, and still requires the header otherwise.
- 2026-11-14: Embeddings default to a local model (see question 1).
- 2026-11-13: Company pages live under `/t/<companyId>/Ã¢â‚¬Â¦`; switching company goes through `/switch/<id>`.
- 2026-11-13: The DB access design is in `docs/decisions/0001-db-access.md`.

## Known gaps carried forward

- Audit entries record the web server's IP, not the user's (review finding 9). Fix with the deploy work.
- Invitation clean-up (purge old ones after 30 days) and the audit log retention period are listed in `docs/privacy.md`.
- Scanned (image-only) PDFs give "no text found"; OCR is not included.
