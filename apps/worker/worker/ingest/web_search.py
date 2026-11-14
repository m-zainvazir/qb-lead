"""Web search connectors: Exa or Tavily (by meaning), Serper (keywords). Paid; key required.

Each is switched off in `sources` until its key is set in the environment. Without a
key the run ends as 'skipped' with a clear reason.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, ClassVar

from core.settings import get_settings
from core.text import html_to_text
from worker.ingest.base import NotConfigured, RawItem, RunContext

RESULTS_PER_QUERY = 10


def _id(url: str) -> str:
    return sha256(url.encode()).hexdigest()[:40]


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def exa_items(data: dict[str, Any], query: str) -> list[RawItem]:
    return [
        RawItem(
            external_id=_id(r["url"]),
            title=r.get("title"),
            body=html_to_text(r.get("text") or r.get("summary") or "")[:8000] or None,
            url=r["url"],
            author_handle=r.get("author"),
            posted_at=_date(r.get("publishedDate")),
            payload={"query": query, "provider": "exa", "score": r.get("score")},
        )
        for r in data.get("results", [])
        if r.get("url")
    ]


def tavily_items(data: dict[str, Any], query: str) -> list[RawItem]:
    return [
        RawItem(
            external_id=_id(r["url"]),
            title=r.get("title"),
            body=html_to_text(r.get("content") or "")[:8000] or None,
            url=r["url"],
            posted_at=_date(r.get("published_date")),
            payload={"query": query, "provider": "tavily", "score": r.get("score")},
        )
        for r in data.get("results", [])
        if r.get("url")
    ]


def serper_items(data: dict[str, Any], query: str) -> list[RawItem]:
    return [
        RawItem(
            external_id=_id(r["link"]),
            title=r.get("title"),
            body=html_to_text(r.get("snippet") or "") or None,
            url=r["link"],
            payload={
                "query": query,
                "provider": "serper",
                "position": r.get("position"),
                "date": r.get("date"),
            },
        )
        for r in data.get("organic", [])
        if r.get("link")
    ]


def _key(name: str) -> str:
    value = getattr(get_settings(), name, None)
    if value is None:
        raise NotConfigured(f"{name.upper()} is not set")
    return str(value.get_secret_value())


class ExaConnector:
    name: ClassVar[str] = "web_exa"
    query_family: ClassVar[str] = "web_search"

    def fetch(self, queries: list[str], since: datetime, ctx: RunContext) -> Iterator[RawItem]:
        key = _key("exa_api_key")
        for query in queries:
            data = ctx.post_json(
                "https://api.exa.ai/search",
                json={
                    "query": query,
                    "numResults": RESULTS_PER_QUERY,
                    "startPublishedDate": since.astimezone(UTC).isoformat(),
                    "contents": {"text": {"maxCharacters": 4000}},
                },
                headers={"x-api-key": key},
            )
            yield from exa_items(data, query)


class TavilyConnector:
    name: ClassVar[str] = "web_tavily"
    query_family: ClassVar[str] = "web_search"

    def fetch(self, queries: list[str], since: datetime, ctx: RunContext) -> Iterator[RawItem]:
        key = _key("tavily_api_key")
        days = max(1, (datetime.now(UTC) - since).days + 1)
        for query in queries:
            data = ctx.post_json(
                "https://api.tavily.com/search",
                json={
                    "query": query,
                    "max_results": RESULTS_PER_QUERY,
                    "days": days,
                    "topic": "general",
                },
                headers={"Authorization": f"Bearer {key}"},
            )
            yield from tavily_items(data, query)


class SerperConnector:
    name: ClassVar[str] = "web_serper"
    query_family: ClassVar[str] = "web_search"

    def fetch(self, queries: list[str], since: datetime, ctx: RunContext) -> Iterator[RawItem]:
        key = _key("serper_api_key")
        for query in queries:
            data = ctx.post_json(
                "https://google.serper.dev/search",
                json={"q": query, "num": RESULTS_PER_QUERY, "tbs": "qdr:w"},
                headers={"X-API-KEY": key},
            )
            yield from serper_items(data, query)
