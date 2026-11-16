"""user_db / system_db against the staging database (run with `make test-db`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from core import db

pytestmark = pytest.mark.db


@pytest.fixture
async def pools() -> AsyncIterator[None]:
    await db.open_pools()
    try:
        yield
    finally:
        await db.close_pools()


def _claims(sub: str) -> dict[str, str]:
    return {"sub": sub, "role": "authenticated", "aud": "authenticated", "email": "t@example.com"}


async def test_user_db_runs_as_authenticated_with_claims(pools: None) -> None:
    sub = str(uuid.uuid4())
    async with db.user_db(_claims(sub)) as conn:
        row = await (
            await conn.execute("select current_user as u, auth.uid()::text as uid")
        ).fetchone()
    assert row == {"u": "authenticated", "uid": sub}


async def test_identity_does_not_leak_between_transactions(pools: None) -> None:
    async with db.user_db(_claims(str(uuid.uuid4()))):
        pass
    # Same pool, raw connection, no SET ROLE: back to the bare login role with no claims.
    async with db._pool("api").connection() as conn:
        row = await (
            await conn.execute(
                "select current_user as u,"
                " coalesce(current_setting('request.jwt.claims', true), '') as claims"
            )
        ).fetchone()
        await conn.rollback()
    assert row == {"u": "app_api", "claims": ""}


async def test_user_db_rejects_non_user_claims(pools: None) -> None:
    with pytest.raises(PermissionError):
        async with db.user_db({"sub": "x", "role": "service_role"}):
            pass
    with pytest.raises(PermissionError):
        async with db.user_db({"role": "authenticated"}):
            pass


async def test_system_db_runs_as_service_role(pools: None) -> None:
    async with db.system_db() as conn:  # noqa: TID251 - test of the system path itself
        row = await (await conn.execute("select current_user as u")).fetchone()
    assert row == {"u": "service_role"}


async def test_bare_api_login_has_no_table_access(pools: None) -> None:
    async with db._pool("api").connection() as conn:
        row = await (
            await conn.execute(
                "select has_table_privilege('public.tenants', 'select') as t,"
                " has_table_privilege('public.audit_log', 'delete') as a"
            )
        ).fetchone()
        await conn.rollback()
    assert row == {"t": False, "a": False}
