"""Link enrichment: fetch the page an item points to, through the guarded fetcher only.

Blocked and failed fetches are written to `fetch_guard_events`, so
`python -m worker.cli fetch-guard-report` can show them.
"""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from psycopg.types.json import Jsonb

from core.db import system_db_sync
from core.net import Blocked, safe_fetch
from core.text import html_to_text

log = logging.getLogger(__name__)

# Sites whose terms forbid automated fetching: we keep the link, never fetch the page.
NO_FETCH_DOMAINS = (
    "upwork.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
)


def _no_fetch(url: str) -> bool:
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in NO_FETCH_DOMAINS)


def _record(url: str, outcome: str, reason: str | None, raw_item_id: UUID) -> None:
    with system_db_sync() as conn:
        conn.execute(
            "insert into public.fetch_guard_events (url, outcome, reason, raw_item_id)"
            " values (%s, %s, %s, %s)",
            (url[:2000], outcome, (reason or "")[:500] or None, raw_item_id),
        )


def enrich(raw_item_id: UUID) -> str:
    with system_db_sync() as conn:
        item = conn.execute(
            "select url, payload ? 'link' as done from public.raw_items where id = %s",
            (raw_item_id,),
        ).fetchone()
    if item is None or not item["url"]:
        return "nothing-to-fetch"
    if item["done"]:
        return "already-enriched"
    url = item["url"]
    if _no_fetch(url):
        _record(url, "blocked", "site terms do not allow fetching (link kept)", raw_item_id)
        return "not-fetched-by-policy"
    try:
        page = safe_fetch(url)
    except Blocked as exc:
        _record(url, "blocked", str(exc), raw_item_id)
        log.warning("fetch_blocked", extra={"url": url[:200], "reason": str(exc)})
        return "blocked"
    except (httpx.HTTPError, OSError) as exc:
        _record(url, "error", f"{type(exc).__name__}: {exc}", raw_item_id)
        return "error"
    text = html_to_text(page.text, limit=5000) if "html" in page.content_type else page.text[:5000]
    with system_db_sync() as conn:
        conn.execute(
            "update public.raw_items set payload = payload || %s where id = %s",
            (Jsonb({"link": {"url": page.url, "status": page.status, "text": text}}), raw_item_id),
        )
    _record(url, "fetched", None, raw_item_id)
    return "fetched"


def report(last: int) -> list[dict[str, object]]:
    with system_db_sync() as conn:
        rows = conn.execute(
            "select created_at, outcome, url, reason from public.fetch_guard_events"
            " order by id desc limit %s",
            (last,),
        ).fetchall()
    return [dict(r) for r in rows]
