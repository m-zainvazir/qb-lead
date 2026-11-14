# Source register

Every lead source: how we access it, its terms, its risk level and when that was checked. Re-read each source's terms every quarter and update the "checked" date. A red source cannot be switched on without a platform admin override, which is written to the audit log.

Risk levels:
- **green:** an official API or a feed the source offers for this use, within its terms
- **amber:** public pages, robots.txt respected, rate limited, with terms that need watching
- **red:** anything needing a login, or against the site's terms. Do not ship without a written decision.

| Source (key) | Access method | Terms | Risk | Cost | Checked | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Hacker News (`hackernews`) | Algolia HN Search API (`hn.algolia.com/api/v1`), no key | https://hn.algolia.com/api, https://news.ycombinator.com/newsguidelines.html | green | free | 2026-11-14 | Search of stories and comments plus the monthly `whoishiring` threads. We store public handles and links only. |
| Web search, Exa (`web_exa`) | Exa search API, key `EXA_API_KEY` | https://exa.ai/terms | green | per call (about $0.005) | 2026-11-14 | **Off** until a key is set. |
| Web search, Tavily (`web_tavily`) | Tavily search API, key `TAVILY_API_KEY` | https://tavily.com/terms | green | per call (about $0.008) | 2026-11-14 | **Off** until a key is set. |
| Web search, Serper (`web_serper`) | Serper Google search API, key `SERPER_API_KEY` | https://serper.dev/terms | green | per call (about $0.001) | 2026-11-14 | **Off** until a key is set. Keyword search. |
| Inbound webhook (`webhook`) | `POST /ingest/<secret>` per company | our own | green | free | 2026-11-14 | The company sends its own leads (forms, n8n). Private to that company. |
| Inbound email (`email`) | Mailgun inbound route to `POST /inbound/email`, signed | https://www.mailgun.com/legal/terms/ | green | Mailgun plan | 2026-11-14 | The user forwards their own alerts. Private to that company. |
| Upwork job alerts (via email) | Parsed from emails the user forwards to us | https://www.upwork.com/legal | amber | free | 2026-11-14 | We never fetch upwork.com pages (on the guarded fetcher's do-not-fetch list); we keep the job link only. |
| Fake (`fake`) | Saved sample data in the repo | n/a | green | n/a | 2026-11-14 | Tests only; off. |

## Planned, not built

| Source | Expected access | Expected risk | Blocker |
| --- | --- | --- | --- |
| X (Twitter) | Official API, strict monthly cap | amber | Paid API tier and key |
| Apify actors for open sites | Apify API | amber | Choose actors, terms per site |
| Job boards | Official feeds or APIs only | green/amber | Pick boards |
| LinkedIn | none acceptable | red | Terms forbid automated access: do not build without a written decision |

## Link fetching

Links taken from outside content are fetched only through `core.net.safe_fetch` (public addresses only, re-checked on every redirect). These sites are never fetched, only linked: upwork.com, linkedin.com, facebook.com, instagram.com, x.com, twitter.com (`NO_FETCH_DOMAINS` in `apps/worker/worker/ingest/enrich.py`).
