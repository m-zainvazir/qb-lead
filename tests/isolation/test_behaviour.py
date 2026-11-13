"""Agency A against Agency B's rows, for every tenant table, at the database level."""

from __future__ import annotations

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import DictRow

from tests.isolation.catalog import TENANT_TABLES
from tests.isolation.conftest import World, act_as, as_owner, expect_sqlstate
from tests.isolation.factories import FACTORIES, TENANT_COLUMN

Conn = psycopg.Connection[DictRow]
TESTABLE = [t for t in TENANT_TABLES if t in FACTORIES]  # missing ones fail test_structure


def _users(world: World, owner: str) -> dict[str, str]:
    return {"owner": owner, "owner_a": world.owner_a, "admin": world.admin}


def _prepare(conn: Conn, world: World, table: str) -> dict[str, object]:
    """Rows for both agencies; returns what A would try to insert into B."""
    as_owner(conn)
    FACTORIES[table](conn, world.tenant_a, _users(world, world.owner_a))
    return FACTORIES[table](conn, world.tenant_b, _users(world, world.owner_b))


def _granted(conn: Conn, table: str, privilege: str) -> bool:
    row = conn.execute(
        "select has_table_privilege('authenticated', format('public.%%I', %s::text), %s)"
        " or has_any_column_privilege('authenticated', format('public.%%I', %s::text), %s) as ok",
        (table, privilege, table, privilege),
    ).fetchone()
    return bool(row and row["ok"])


def _expect_denied_or_zero(conn: Conn, query: sql.Composable, params: tuple[object, ...]) -> None:
    try:
        with conn.transaction():
            cur = conn.execute(query, params)
            count = cur.rowcount if cur.description is None else len(cur.fetchall())
    except psycopg.errors.InsufficientPrivilege:
        return
    assert count == 0, f"{count} row(s) of the other agency were reachable: {query!r}"


@pytest.mark.parametrize("table", TESTABLE)
def test_a_cannot_read_b(conn: Conn, world: World, table: str) -> None:
    _prepare(conn, world, table)
    col = TENANT_COLUMN.get(table, "tenant_id")
    act_as(conn, world.claims(world.owner_a))
    q = sql.SQL("select * from {} where {} = %s").format(
        sql.Identifier("public", table), sql.Identifier(col)
    )
    _expect_denied_or_zero(conn, q, (world.tenant_b,))


@pytest.mark.parametrize("table", TESTABLE)
def test_a_sees_own_rows(conn: Conn, world: World, table: str) -> None:
    """Positive control, so the denial tests above are not passing vacuously."""
    _prepare(conn, world, table)
    if not _granted(conn, table, "SELECT"):
        pytest.skip(f"{table}: users have no direct read access")
    col = TENANT_COLUMN.get(table, "tenant_id")
    act_as(conn, world.claims(world.owner_a))
    rows = conn.execute(
        sql.SQL("select 1 from {} where {} = %s").format(
            sql.Identifier("public", table), sql.Identifier(col)
        ),
        (world.tenant_a,),
    ).fetchall()
    assert len(rows) >= 1


@pytest.mark.parametrize("table", TESTABLE)
def test_a_cannot_insert_into_b(conn: Conn, world: World, table: str) -> None:
    values = _prepare(conn, world, table)
    if table == "tenants":
        values = {"id": world.tenant_b, **values}
    act_as(conn, world.claims(world.owner_a))
    q = sql.SQL("insert into {} ({}) values ({})").format(
        sql.Identifier("public", table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)),
    )
    with expect_sqlstate(conn, "42501"):
        conn.execute(q, tuple(values.values()))


@pytest.mark.parametrize("table", TESTABLE)
def test_a_cannot_update_b(conn: Conn, world: World, table: str) -> None:
    _prepare(conn, world, table)
    updatable = conn.execute(
        "select column_name from information_schema.columns where table_schema = 'public'"
        " and table_name = %s"
        " and has_column_privilege('authenticated', format('public.%%I', %s::text), column_name,"
        "  'UPDATE') order by ordinal_position limit 1",
        (table, table),
    ).fetchone()
    if updatable is None:
        pytest.skip(f"{table}: users cannot update any column")
    col = TENANT_COLUMN.get(table, "tenant_id")
    target = updatable["column_name"]
    act_as(conn, world.claims(world.owner_a))
    q = sql.SQL("update {} set {} = {} where {} = %s").format(
        sql.Identifier("public", table),
        sql.Identifier(target),
        sql.Identifier(target),
        sql.Identifier(col),
    )
    _expect_denied_or_zero(conn, q, (world.tenant_b,))


@pytest.mark.parametrize("table", TESTABLE)
def test_a_cannot_delete_b(conn: Conn, world: World, table: str) -> None:
    _prepare(conn, world, table)
    col = TENANT_COLUMN.get(table, "tenant_id")
    act_as(conn, world.claims(world.owner_a))
    q = sql.SQL("delete from {} where {} = %s").format(
        sql.Identifier("public", table), sql.Identifier(col)
    )
    _expect_denied_or_zero(conn, q, (world.tenant_b,))


@pytest.mark.parametrize("table", TESTABLE)
def test_anon_reads_nothing(conn: Conn, world: World, table: str) -> None:
    _prepare(conn, world, table)
    act_as(conn, None)
    q = sql.SQL("select * from {}").format(sql.Identifier("public", table))
    _expect_denied_or_zero(conn, q, ())
