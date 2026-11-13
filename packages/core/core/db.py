"""Database access layer shared by the API and the worker.

See docs/decisions/0001-db-access.md. This is the only module that creates database
connections. Two paths, clearly named:

* ``user_db(claims)``: acts as the signed-in user. Row-level security applies.
* ``system_db()``: acts as ``service_role`` and bypasses RLS. Only ``apps/worker`` and
  ``apps/api/api/admin`` may import it (ruff TID251 plus a test enforce this).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import psycopg
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from core.logging import client_ip_var, request_id_var
from core.settings import get_settings

log = logging.getLogger(__name__)

Conn = AsyncConnection[DictRow]

_pools: dict[str, AsyncConnectionPool[Conn]] = {}


async def _configure(conn: Conn) -> None:
    timeout = get_settings().db_statement_timeout_ms
    await conn.execute("select set_config('statement_timeout', %s, false)", (f"{int(timeout)}ms",))
    await conn.commit()


def _make_pool(name: str, conninfo: str) -> AsyncConnectionPool[Conn]:
    s = get_settings()
    return AsyncConnectionPool(
        conninfo,
        connection_class=AsyncConnection[DictRow],
        kwargs={"row_factory": dict_row, "autocommit": False},
        name=name,
        min_size=s.db_pool_min,
        max_size=s.db_pool_max,
        open=False,
        configure=_configure,
        timeout=10,
    )


async def open_pools() -> None:
    """Open the pools at service startup (FastAPI lifespan / worker init)."""
    s = get_settings()
    if "api" not in _pools:
        _pools["api"] = _make_pool("api", s.database_url_api.get_secret_value())
    if "system" not in _pools:
        _pools["system"] = _make_pool("system", s.database_url_system.get_secret_value())
    for pool in _pools.values():
        await pool.open(wait=False)


async def close_pools() -> None:
    for pool in _pools.values():
        await pool.close()
    _pools.clear()


def _pool(name: str) -> AsyncConnectionPool[Conn]:
    try:
        return _pools[name]
    except KeyError as exc:  # pragma: no cover - programming error
        raise RuntimeError("Database pools are not open; call open_pools() at startup.") from exc


async def _set_request_context(conn: Conn) -> None:
    # Transaction-local (`true`): nothing survives into the next use of this connection.
    await conn.execute(
        "select set_config('app.request_id', %s, true), set_config('app.client_ip', %s, true)",
        (request_id_var.get() or "", client_ip_var.get() or ""),
    )


@asynccontextmanager
async def user_db(claims: Mapping[str, Any]) -> AsyncIterator[Conn]:
    """One transaction as the signed-in user; row-level security applies.

    ``claims`` must come from a JWT this service verified itself (api.auth), never
    from the client directly.
    """
    sub = claims.get("sub")
    if not sub or claims.get("role") != "authenticated":
        raise PermissionError("user_db() needs verified claims for an authenticated user")
    async with _pool("api").connection() as conn, conn.transaction():
        await conn.execute("set local role authenticated")
        await conn.execute(
            "select set_config('request.jwt.claims', %s, true),"
            " set_config('request.jwt.claim.sub', %s, true),"
            " set_config('request.jwt.claim.role', 'authenticated', true)",
            (json.dumps(dict(claims), default=str), str(sub)),
        )
        await _set_request_context(conn)
        yield conn


@asynccontextmanager
async def system_db() -> AsyncIterator[Conn]:
    """One transaction as service_role (bypasses RLS). Worker and admin module only."""
    async with _pool("system").connection() as conn, conn.transaction():
        await conn.execute("set local role service_role")
        await _set_request_context(conn)
        yield conn


@contextmanager
def system_db_sync() -> Iterator[psycopg.Connection[DictRow]]:
    """Synchronous system path for Celery tasks (the worker is not async).

    Same rules as system_db(): worker and admin only. One short connection per use;
    the transaction commits when the block exits without an error.
    """
    url = get_settings().database_url_system.get_secret_value()
    with psycopg.connect(url, row_factory=dict_row, connect_timeout=10, autocommit=True) as conn:
        conn.execute("set statement_timeout = '60s'")
        with conn.transaction():
            conn.execute("set local role service_role")
            yield conn
