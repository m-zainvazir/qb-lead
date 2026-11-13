# Build status

Updated by Claude Code on every run of the build loop. Newest first inside each section.
Last update: 2026-11-14.

## Where things stand

| Module | State | Notes |
| --- | --- | --- |
| 0 Foundation (local slice) | Done locally | Staging, branch protection and the first CI run are deferred (no remote yet) |
| 1 Tenants, logins and isolation | Done, except your browser checks | All 11 terminal tests pass; security review fixed (`docs/reviews/2026-11-13-module-01.md`) |
| 2 Catalogue and onboarding | **In progress** | Task list below |
| 3–12 | Not started | Built in order |

## Module 2 task list (in place of a plan-mode approval, since the loop runs unattended)

- [x] M2-1 Catalogue migrations (`services`, `problems`, `technologies`, links, `markets`, `signal_types`, `onboarding_questions`) and seed data: AI automation, voice agents, web development
- [ ] M2-2 Tenant tables from the module 1 template: `tenant_profiles` (versioned), `tenant_services`, `tenant_markets`, `tenant_signals`, `tenant_exclusions`, `portfolio_items`, `profile_compilations`, `service_fingerprints`, `onboarding_progress`; isolation factories
- [ ] M2-3 Questionnaire as data; API to read questions, save answers and resume; wizard rendered from data
- [ ] M2-4 Profile compiler as an idempotent worker job (search terms per source, versioned)
- [ ] M2-5 Embeddings behind an interface (model name and size stored with every vector); `re-embed` command; ADR 0002; minimal `metered_call()` that records cost
- [ ] M2-6 Portfolio upload: private bucket, tenant folders, storage policies, size cap, content-type sniffing, extraction in the worker with limits, signed short-lived links
- [ ] M2-7 Preview screen ("here is what we will look for") from a fixed set of sample posts
- [ ] M2-8 Admin: add a service, market, signal or question as data
- [ ] Terminal tests, `rls-test`, Done-when list

## Questions for you

1. **Embeddings provider.** No API key is configured, so I used a local, free model (fastembed `BAAI/bge-small-en-v1.5`, 384 dimensions) behind an interface. Do you want OpenAI (`text-embedding-3-small`), Voyage or another provider later? Switching is a setting plus `python -m worker.cli re-embed`.
2. **Git identity.** Commits use "Muhammad Zain" and your work email (repo-local setting). Change it if needed.
3. **GitHub remote and staging host.** Needed for CI and module 0's staging step. Tell me the repo URL and host (Railway or Hetzner + Coolify) when ready.

## Open for you (tests and manual steps)

### Module 1
- [ ] Manual tests 1–8 in a browser (`docs/plans/module-01-tenants-and-isolation.md`). Emails arrive at http://127.0.0.1:54324. Start with `make dev`, or Supabase + `make up` + `cd apps/web && npm run dev`.
- [ ] The first platform admin on a real environment: enrol an authenticator at `/admin/mfa` first, then run `supabase/snippets/create_platform_admin.sql`.
- [ ] Note: a page for another company shows "Not found" but with HTTP status 200, because the page streams. No data from the other company is in the response.

### Module 0
- [ ] Install the plugins listed in `docs/plans/00-overview.md` with `/plugin install …`
- [ ] Open a new terminal so `make` and `gitleaks` (installed with winget) are on PATH
- [ ] Clone into a fresh folder, run `make install && make env && make dev`, and check it works in under 30 minutes
- [ ] Add a GitHub remote, push, and check the CI run (the `database` job runs the isolation suite)

## Decisions made without you (easy to change)

- 2026-11-14: Module 2's terminal tests call the API without `X-Tenant-Id`. The API now uses your company when you belong to exactly one, and still requires the header otherwise.
- 2026-11-14: Embeddings default to a local model (see question 1).
- 2026-11-13: Company pages live under `/t/<companyId>/…`; switching company goes through `/switch/<id>`.
- 2026-11-13: The DB access design is in `docs/decisions/0001-db-access.md`.

## Known gaps carried forward

- Audit entries record the web server's IP, not the user's (review finding 9). Fix with the deploy work.
- Invitation clean-up (purge old ones after 30 days) and the audit log retention period are listed in `docs/privacy.md`.
