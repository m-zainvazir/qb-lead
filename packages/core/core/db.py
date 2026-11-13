"""Database access layer shared by the API and the worker.

See docs/decisions/0001-db-access.md. Module 1 adds `user_db()` and `system_db()`.
This is the only module that may create a database connection pool.
"""

from __future__ import annotations

import logging

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from core.settings import get_settings

log = logging.getLogger(__name__)

_pools: dict[str, AsyncConnectionPool] = {}


async def _configure(conn: AsyncConnection) -> None:
    timeout = get_settings().db_statement_timeout_ms
    await conn.execute("select set_config('statement_timeout', %s, false)", (f"{int(timeout)}ms",))
    await conn.commit()


def _make_pool(name: str, conninfo: str) -> AsyncConnectionPool:
    s = get_settings()
    return AsyncConnectionPool(
        conninfo,
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


def _pool(name: str) -> AsyncConnectionPool:
    try:
        return _pools[name]
    except KeyError as exc:  # pragma: no cover - programming error
        raise RuntimeError("Database pools are not open; call open_pools() at startup.") from exc
