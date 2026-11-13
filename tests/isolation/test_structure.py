"""Structural checks on every table in `public`."""

from __future__ import annotations

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.isolation.catalog import PUBLIC_TABLES, TENANT_TABLES
from tests.isolation.conftest import World
from tests.isolation.factories import FACTORIES, TENANT_COLUMN

Conn = psycopg.Connection[DictRow]


def test_tables_were_discovered() -> None:
    assert {"tenants", "memberships", "invitations", "audit_log"} <= set(TENANT_TABLES)


def test_no_public_table_without_rls(conn: Conn) -> None:  # terminal test 8
    rows = conn.execute(
        "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
        " where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    ).fetchall()
    assert rows == []


@pytest.mark.parametrize("table", PUBLIC_TABLES)
def test_rls_enabled_and_forced(conn: Conn, table: str) -> None:
    row = conn.execute(
        "select relrowsecurity, relforcerowsecurity from pg_class"
        " where oid = format('public.%%I', %s::text)::regclass",
        (table,),
    ).fetchone()
    assert row == {"relrowsecurity": True, "relforcerowsecurity": True}


@pytest.mark.parametrize("table", PUBLIC_TABLES)
def test_anon_has_no_privileges(conn: Conn, table: str) -> None:
    granted = conn.execute(
        "select p from unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
        " 'REFERENCES','TRIGGER']) p"
        " where has_table_privilege('anon', format('public.%%I', %s::text), p)"
        "    or (p in ('SELECT','INSERT','UPDATE')"
        "        and has_any_column_privilege('anon', format('public.%%I', %s::text), p))",
        (table, table),
    ).fetchall()
    assert granted == []


@pytest.mark.parametrize("table", PUBLIC_TABLES)
def test_users_cannot_truncate_or_attach_triggers(conn: Conn, table: str) -> None:
    granted = conn.execute(
        "select r || ':' || p as g from unnest(array['authenticated','service_role']) r,"
        " unnest(array['TRUNCATE','REFERENCES','TRIGGER']) p"
        " where has_table_privilege(r, format('public.%%I', %s::text), p)",
        (table,),
    ).fetchall()
    assert granted == []


@pytest.mark.parametrize("table", PUBLIC_TABLES)
def test_no_policy_allows_everything(conn: Conn, table: str) -> None:
    open_policies = conn.execute(
        "select policyname from pg_policies where schemaname = 'public' and tablename = %s"
        " and (trim(coalesce(qual, '')) = 'true' or trim(coalesce(with_check, '')) = 'true')",
        (table,),
    ).fetchall()
    assert open_policies == []


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_tenant_policies_check_membership(conn: Conn, table: str) -> None:
    policies = conn.execute(
        "select policyname, cmd, coalesce(qual, '') || ' ' || coalesce(with_check, '') as expr"
        " from pg_policies where schemaname = 'public' and tablename = %s",
        (table,),
    ).fetchall()
    weak = [
        p["policyname"]
        for p in policies
        if "is_member(" not in p["expr"] and "has_role(" not in p["expr"]
    ]
    assert weak == [], f"policies on {table} that do not check membership: {weak}"


@pytest.mark.parametrize("table", [t for t in TENANT_TABLES if t != "tenants"])
def test_tenant_column_is_indexed(conn: Conn, table: str) -> None:
    row = conn.execute(
        "select 1 from pg_index i join pg_attribute a"
        "   on a.attrelid = i.indrelid and a.attnum = i.indkey[0]"
        " where i.indrelid = format('public.%%I', %s::text)::regclass"
        "   and a.attname = 'tenant_id'",
        (table,),
    ).fetchone()
    assert row is not None, f"{table}.tenant_id needs an index whose first column is tenant_id"


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_every_tenant_table_has_a_factory(table: str) -> None:
    assert table in FACTORIES, (
        f"New tenant table {table!r}: add a factory to tests/isolation/factories.py "
        "so the isolation suite can test it."
    )
    TENANT_COLUMN.get(table, "tenant_id")


def test_world_is_two_separate_agencies(world: World) -> None:
    assert world.tenant_a != world.tenant_b
