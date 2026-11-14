"""Hacker News via the free Algolia search API (green: official, open API, no key).

Two passes per run:
  1. full-text search of stories and comments for the planned queries since the last run;
  2. the monthly "Who is hiring?" and "Freelancer? Seeking freelancer?" threads posted by
     the `whoishiring` account: their new comments since the last run.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from core.text import html_to_text
from worker.ingest.base import RawItem, RunContext

API = "https://hn.algolia.com/api/v1"
HN_ITEM = "https://news.ycombinator.com/item?id="
HN_USER = "https://news.ycombinator.com/user?id="
HITS_PER_PAGE = 50
MAX_THREAD_PAGES = 5
THREAD_TITLES = ("who is hiring", "freelancer? seeking freelancer")


def to_item(hit: dict[str, Any], kind: str, thread: str | None = None) -> RawItem:
    """Pure function: one Algolia hit -> RawItem."""
    object_id = str(hit["objectID"])
    is_comment = "comment" in (hit.get("_tags") or []) or hit.get("comment_text") is not None
    text = html_to_text(hit.get("comment_text") or hit.get("story_text") or "")
    title = hit.get("title") or (
        f"Comment in: {hit.get('story_title')}" if hit.get("story_title") else "Hacker News comment"
    )
    if is_comment and text:
        first_line = text.split("\n", 1)[0]
        title = first_line[:200] if thread else title
    created = hit.get("created_at_i")
    return RawItem(
        external_id=object_id,
        title=title,
        body=text or None,
        url=hit.get("url") if hit.get("url") and not is_comment else f"{HN_ITEM}{object_id}",
        author_handle=hit.get("author"),
        author_url=f"{HN_USER}{hit['author']}" if hit.get("author") else None,
        posted_at=datetime.fromtimestamp(created, tz=UTC) if created else None,
        payload={
            "kind": kind,
            "thread": thread,
            "story_id": hit.get("story_id"),
            "story_title": hit.get("story_title"),
            "points": hit.get("points"),
            "tags": hit.get("_tags"),
        },
    )


class HackerNewsConnector:
    name: ClassVar[str] = "hackernews"
    query_family: ClassVar[str] = "reddit"  # short plain phrases suit Algolia full-text search

    def fetch(self, queries: list[str], since: datetime, ctx: RunContext) -> Iterator[RawItem]:
        since_i = int(since.timestamp())
        seen: set[str] = set()
        for query in queries:
            data = ctx.get_json(
                f"{API}/search_by_date",
                params={
                    "query": query,
                    "tags": "(story,comment)",
                    "numericFilters": f"created_at_i>{since_i}",
                    "hitsPerPage": HITS_PER_PAGE,
                },
                operation="search",
            )
            for hit in data.get("hits", []):
                if str(hit["objectID"]) not in seen:
                    seen.add(str(hit["objectID"]))
                    yield to_item(hit, "search")
        if ctx.settings.get("include_hiring_threads", True):
            yield from self._hiring_threads(since_i, seen, ctx)

    def _hiring_threads(self, since_i: int, seen: set[str], ctx: RunContext) -> Iterator[RawItem]:
        month_ago = int((datetime.now(UTC) - timedelta(days=40)).timestamp())
        stories = ctx.get_json(
            f"{API}/search_by_date",
            params={
                "tags": "story,author_whoishiring",
                "hitsPerPage": 10,
                "numericFilters": f"created_at_i>{month_ago}",
            },
            operation="threads",
        )
        for story in stories.get("hits", []):
            title = (story.get("title") or "").lower()
            if not any(t in title for t in THREAD_TITLES):
                continue
            for page in range(MAX_THREAD_PAGES):
                data = ctx.get_json(
                    f"{API}/search_by_date",
                    params={
                        "tags": f"comment,story_{story['objectID']}",
                        "numericFilters": f"created_at_i>{since_i}",
                        "hitsPerPage": 100,
                        "page": page,
                    },
                    operation="thread_comments",
                )
                for hit in data.get("hits", []):
                    # only top-level answers (direct replies to the thread)
                    if str(hit.get("parent_id")) != str(story["objectID"]):
                        continue
                    if str(hit["objectID"]) not in seen:
                        seen.add(str(hit["objectID"]))
                        yield to_item(hit, "hiring_thread", thread=story.get("title"))
                if page + 1 >= int(data.get("nbPages", 0)):
                    break
