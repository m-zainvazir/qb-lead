"""Connector interface. A connector only collects: it never judges or filters by meaning.

A new source is one class (registered in `worker.ingest.registry`) and one row in
`sources`. See the `connector-new` skill for the full checklist.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Protocol
from uuid import UUID

import httpx

from core.metering import metered_call


@dataclass(frozen=True)
class RawItem:
    external_id: str
    title: str | None = None
    body: str | None = None
    url: str | None = None
    author_handle: str | None = None  # public handle only (personal data rule)
    author_url: str | None = None
    posted_at: datetime | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext:
    source_key: str
    run_id: UUID
    settings: dict[str, Any]
    cost_per_call_usd: float
    timeout_s: float = 20.0

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        operation: str = "fetch",
    ) -> Any:
        """One metered GET: recorded in usage_events, refused when the monthly cap is reached."""

        def call() -> Any:
            res = httpx.get(url, params=params, headers=headers, timeout=self.timeout_s)
            res.raise_for_status()
            return res.json()

        return metered_call(
            call,
            provider=self.source_key,
            operation=f"{self.source_key}.{operation}",
            tenant_id=None,
            units=1,
            unit="call",
            unit_cost_usd=self.cost_per_call_usd,
            source_key=self.source_key,
            run_id=self.run_id,
            metadata={"url": url.split("?")[0]},
        )

    def post_json(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
        operation: str = "search",
    ) -> Any:
        def call() -> Any:
            res = httpx.post(url, json=json, headers=headers, timeout=self.timeout_s)
            res.raise_for_status()
            return res.json()

        return metered_call(
            call,
            provider=self.source_key,
            operation=f"{self.source_key}.{operation}",
            tenant_id=None,
            units=1,
            unit="call",
            unit_cost_usd=self.cost_per_call_usd,
            source_key=self.source_key,
            run_id=self.run_id,
            metadata={"url": url},
        )


class Connector(Protocol):
    name: ClassVar[str]
    query_family: ClassVar[
        str
    ]  # which compiled query list it uses: "reddit" | "web_search" | "job_boards"

    def fetch(self, queries: list[str], since: datetime, ctx: RunContext) -> Iterator[RawItem]: ...


class NotConfigured(Exception):
    """The connector needs a key or setting that is missing; the run is skipped cleanly."""
