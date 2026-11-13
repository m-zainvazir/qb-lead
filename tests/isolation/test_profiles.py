"""Module 2 rules: profile versioning, who may edit, portfolio paths, system-only outputs."""

from __future__ import annotations

import psycopg
from psycopg.rows import DictRow

from tests.isolation.conftest import World, act_as, as_owner, expect_sqlstate
from tests.isolation.factories import ZERO_VECTOR

Conn = psycopg.Connection[DictRow]


def _profile(conn: Conn, tenant: str) -> dict[str, object]:
    as_owner(conn)
    conn.execute(
        "insert into public.tenant_profiles (tenant_id, type) values (%s, 'agency')"
        " on conflict (tenant_id) do nothing",
        (tenant,),
    )
    row = conn.execute(
        "select version, compile_status from public.tenant_profiles where tenant_id = %s",
        (tenant,),
    ).fetchone()
    assert row is not None
    return row


def test_one_save_bumps_the_version_once(conn: Conn, world: World) -> None:
    # Everything stays inside the rolled-back test transaction. Pretend the profile was
    # last changed by an earlier transaction, then make one "save" with several writes.
    before = _profile(conn, world.tenant_a)
    conn.execute(
        "update public.tenant_profiles set version_txid = 0 where tenant_id = %s",
        (world.tenant_a,),
    )
    act_as(conn, world.claims(world.owner_a))
    conn.execute(
        "update public.tenant_profiles set tone = 'friendly', min_budget_usd = 2000"
        " where tenant_id = %s",
        (world.tenant_a,),
    )
    conn.execute(
        "insert into public.tenant_exclusions (tenant_id, value) values (%s, 'iso-crypto')",
        (world.tenant_a,),
    )
    conn.execute(
        "insert into public.tenant_services (tenant_id, custom_name) values (%s, 'Iso widgets')",
        (world.tenant_a,),
    )
    as_owner(conn)
    after = conn.execute(
        "select version, compile_status from public.tenant_profiles where tenant_id = %s",
        (world.tenant_a,),
    ).fetchone()
    assert after == {"version": int(str(before["version"])) + 1, "compile_status": "pending"}


def test_members_cannot_edit_the_profile(conn: Conn, world: World) -> None:
    _profile(conn, world.tenant_a)
    act_as(conn, world.claims(world.member_a))
    cur = conn.execute(
        "update public.tenant_profiles set tone = 'direct' where tenant_id = %s", (world.tenant_a,)
    )
    assert cur.rowcount == 0
    with expect_sqlstate(conn, "42501"):
        conn.execute(
            "insert into public.tenant_exclusions (tenant_id, value) values (%s, 'x')",
            (world.tenant_a,),
        )


def test_users_cannot_set_version_or_compile_status(conn: Conn, world: World) -> None:
    _profile(conn, world.tenant_a)
    act_as(conn, world.claims(world.owner_a))
    for column in ("version", "compile_status", "compiled_version"):
        with expect_sqlstate(conn, "42501"):
            conn.execute(
                f"update public.tenant_profiles set {column} = {column} where tenant_id = %s",
                (world.tenant_a,),
            )


def test_portfolio_row_cannot_point_into_another_company(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    with expect_sqlstate(conn, "23514"):
        conn.execute(
            "insert into public.portfolio_items"
            " (tenant_id, title, file_path, mime_type, size_bytes)"
            " values (%s, 'Mine', %s, 'application/pdf', 10)",
            (world.tenant_a, f"{world.tenant_b}/their-file.pdf"),
        )
    with expect_sqlstate(conn, "23514"):
        conn.execute(
            "insert into public.portfolio_items"
            " (tenant_id, title, file_path, mime_type, size_bytes)"
            " values (%s, 'Mine', %s, 'application/pdf', 10)",
            (world.tenant_a, f"{world.tenant_a}/../{world.tenant_b}/x.pdf"),
        )


def test_users_cannot_write_compiled_outputs(conn: Conn, world: World) -> None:
    act_as(conn, world.claims(world.owner_a))
    with expect_sqlstate(conn, "42501"):
        conn.execute(
            "insert into public.profile_compilations (tenant_id, profile_version) values (%s, 1)",
            (world.tenant_a,),
        )
    with expect_sqlstate(conn, "42501"):
        conn.execute(
            "update public.portfolio_items set summary = 'forged', embedding = %s"
            " where tenant_id = %s",
            (ZERO_VECTOR, world.tenant_a),
        )


def test_custom_services_stay_private(conn: Conn, world: World) -> None:
    as_owner(conn)
    conn.execute(
        "insert into public.tenant_services (tenant_id, custom_name) values (%s, 'Secret sauce')",
        (world.tenant_b,),
    )
    act_as(conn, world.claims(world.owner_a))
    rows = conn.execute(
        "select 1 from public.tenant_services where custom_name = 'Secret sauce'"
    ).fetchall()
    assert rows == []
