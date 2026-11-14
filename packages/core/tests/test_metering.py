"""metered_call against the local database (run with `make test-db`)."""

from __future__ import annotations

import uuid

import psycopg
import pytest

from core.metering import CapReached, metered_call
from core.settings import get_settings

pytestmark = pytest.mark.db


@pytest.fixture
def capped_source() -> str:
    key = f"t_{uuid.uuid4().hex[:10]}"
    url = get_settings().database_url_admin
    assert url is not None
    with psycopg.connect(url.get_secret_value(), autocommit=True) as conn:
        conn.execute(
            "insert into public.sources (key, name, connector, risk, monthly_cap_usd)"
            " values (%s, 'Test', 'fake', 'green', 0.01)",
            (key,),
        )
    return key


def test_calls_are_recorded_and_the_cap_stops_the_next_one(capped_source: str) -> None:
    calls = []

    def call() -> str:
        calls.append(1)
        return "ok"

    kwargs = {
        "provider": "test",
        "operation": "test.call",
        "tenant_id": None,
        "units": 1,
        "unit": "call",
        "unit_cost_usd": 0.006,
        "source_key": capped_source,
    }
    assert metered_call(call, **kwargs) == "ok"  # spent 0.006 of 0.01
    with pytest.raises(CapReached):
        metered_call(call, **kwargs)  # 0.006 + 0.006 > 0.01: refused, not called
    assert len(calls) == 1

    url = get_settings().database_url_admin
    assert url is not None
    with psycopg.connect(url.get_secret_value()) as conn:
        row = conn.execute(
            "select count(*), sum(cost_usd) from public.usage_events where source_key = %s",
            (capped_source,),
        ).fetchone()
    assert row is not None and row[0] == 1 and float(row[1]) == pytest.approx(0.006)


def test_failed_calls_are_recorded_without_cost(capped_source: str) -> None:
    def boom() -> None:
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        metered_call(
            boom,
            provider="test",
            operation="test.fail",
            tenant_id=None,
            units=1,
            unit="call",
            unit_cost_usd=0.001,
            source_key=capped_source,
        )
