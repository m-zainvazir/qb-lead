"""Tenant isolation suite: `pytest tests/isolation -q` against the LOCAL stack.

Uses the real local `.env` (not the fake unit-test environment), refuses anything that
is not a local Supabase, and seeds Agency A / Agency B with `api.seed_test`.
Every database test runs inside one transaction that is rolled back.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
import pytest
from psycopg.rows import DictRow, dict_row

ROOT = Path(__file__).resolve().parents[2]

# The root conftest fills a fake environment for unit tests; drop it here so the
# settings come from the real local .env.
os.environ["LEADGEN_USE_REAL_ENV"] = "1"
for key in (
    "APP_ENV",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "DATABASE_URL_API",
    "DATABASE_URL_SYSTEM",
    "REDIS_URL",
    "GIT_COMMIT",
):
    os.environ.pop(key, None)
os.chdir(ROOT)  # pydantic-settings reads ./.env

from api import seed_test
from core.settings import get_settings

get_settings.cache_clear()


@dataclass(frozen=True)
class World:
    tenant_a: str
    tenant_b: str
    owner_a: str
    member_a: str
    owner_b: str
    admin: str
    env: dict[str, str]

    def claims(self, user_id: str, email: str = "") -> dict[str, Any]:
        return {"sub": user_id, "role": "authenticated", "aud": "authenticated", "email": email}


@pytest.fixture(scope="session")
def world() -> World:
    s = get_settings()
    host = urlparse(s.supabase_url).hostname
    if host not in ("127.0.0.1", "localhost") or s.is_production:
        pytest.exit(f"isolation suite runs against a local stack only (got {host})", 2)
    seed_test.run()
    env: dict[str, str] = {}
    for line in (ROOT / ".env.test.local").read_text(encoding="utf-8").splitlines():
        if line.startswith("export "):
            k, _, v = line[len("export ") :].partition("=")
            env[k] = shlex.split(v)[0]
    return World(
        tenant_a=env["TENANT_A"],
        tenant_b=env["TENANT_B"],
        owner_a=env["USER_OWNER_A"],
        member_a=env["USER_MEMBER_A"],
        owner_b=env["USER_OWNER_B"],
        admin=env["USER_ADMIN"],
        env=env,
    )


@pytest.fixture
def conn(world: World) -> Iterator[psycopg.Connection[DictRow]]:
    """Admin connection inside a transaction that is always rolled back."""
    url = get_settings().database_url_admin
    assert url is not None
    with psycopg.connect(url.get_secret_value(), row_factory=dict_row) as c:
        try:
            yield c
        finally:
            c.rollback()


def act_as(conn: psycopg.Connection[DictRow], claims: dict[str, Any] | None) -> None:
    """Switch the current transaction to a signed-in user (or anon when claims is None)."""
    conn.execute("reset role")
    if claims is None:
        conn.execute("set local role anon")
        conn.execute("select set_config('request.jwt.claims', '{\"role\":\"anon\"}', true)")
        return
    import json

    conn.execute("set local role authenticated")
    conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))


def as_owner(conn: psycopg.Connection[DictRow]) -> None:
    conn.execute("reset role")


@contextmanager
def expect_sqlstate(conn: psycopg.Connection[Any], sqlstate: str) -> Iterator[None]:
    """The block must fail with exactly this SQLSTATE (in a savepoint, so the test goes on)."""
    with pytest.raises(psycopg.Error) as info, conn.transaction():
        yield
    assert info.value.sqlstate == sqlstate, (
        f"expected {sqlstate}, got {info.value.sqlstate}: {info.value}"
    )
