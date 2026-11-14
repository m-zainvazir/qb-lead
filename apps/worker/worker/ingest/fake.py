"""Fake connector: reads saved sample data. Used by tests and to try the pipeline offline."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from core.metering import metered_call
from worker.ingest.base import RawItem, RunContext

SAMPLES = Path(__file__).with_name("samples") / "fake.json"


class FakeConnector:
    name: ClassVar[str] = "fake"
    query_family: ClassVar[str] = "reddit"

    def fetch(self, queries: list[str], since: datetime, ctx: RunContext) -> Iterator[RawItem]:
        # One "call" per run, metered like a real source (so caps can be tested).
        data = metered_call(
            lambda: json.loads(SAMPLES.read_text(encoding="utf-8")),
            provider="fake",
            operation="fake.read",
            tenant_id=None,
            units=1,
            unit="call",
            unit_cost_usd=ctx.cost_per_call_usd,
            source_key=ctx.source_key,
            run_id=ctx.run_id,
        )
        for row in data:
            yield RawItem(
                external_id=row["id"],
                title=row["title"],
                body=row["body"],
                url=row.get("url"),
                author_handle=row.get("author"),
                posted_at=datetime.fromisoformat(row["posted_at"]).astimezone(UTC),
                payload=row,
            )
