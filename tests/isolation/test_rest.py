"""The same wall through Supabase's REST API with real tokens (terminal tests 1-4) and
through our own API (terminal tests 5-7)."""

from __future__ import annotations

import httpx
import pytest

from tests.isolation.conftest import World


@pytest.fixture(scope="module")
def rest(world: World) -> httpx.Client:
    return httpx.Client(
        base_url=f"{world.env['SUPA']}/rest/v1", headers={"apikey": world.env["ANON"]}, timeout=15
    )


@pytest.fixture(scope="module")
def api(world: World) -> httpx.Client:
    client = httpx.Client(base_url=world.env["API"], timeout=15)
    try:
        client.get("/healthz").raise_for_status()
    except httpx.HTTPError:
        pytest.skip("API is not running (make up)")
    return client


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("table", ["tenants", "memberships", "invitations", "audit_log"])
def test_no_login_gets_no_rows(rest: httpx.Client, table: str) -> None:  # test 1
    res = rest.get(f"/{table}", params={"select": "*"})
    assert res.status_code == 401 or res.json() == []


def test_a_cannot_read_b_memberships(rest: httpx.Client, world: World) -> None:  # test 2
    res = rest.get(
        "/memberships",
        params={"tenant_id": f"eq.{world.tenant_b}", "select": "*"},
        headers=_bearer(world.env["JWT_A"]),
    )
    assert res.status_code == 200 and res.json() == []


def test_a_sees_only_own_company(rest: httpx.Client, world: World) -> None:
    res = rest.get("/tenants", params={"select": "id"}, headers=_bearer(world.env["JWT_A"]))
    assert res.status_code == 200
    assert {row["id"] for row in res.json()} == {world.tenant_a}


def test_a_cannot_write_into_b(rest: httpx.Client, world: World) -> None:  # test 3
    res = rest.post(
        "/invitations",
        headers=_bearer(world.env["JWT_A"]),
        json={"tenant_id": world.tenant_b, "email": "x@example.com", "role": "admin"},
    )
    assert res.status_code in (401, 403)
    assert res.json().get("code") == "42501"


def test_member_cannot_promote_self(rest: httpx.Client, world: World) -> None:  # test 4
    res = rest.patch(
        "/memberships",
        params={"user_id": f"eq.{world.member_a}"},
        headers={**_bearer(world.env["JWT_MEMBER_A"]), "Prefer": "return=representation"},
        json={"role": "owner"},
    )
    assert res.status_code == 200 and res.json() == []


def test_tampered_token_is_rejected(api: httpx.Client, world: World) -> None:  # test 5
    assert api.get("/me", headers=_bearer(world.env["JWT_A"] + "x")).status_code == 401


def test_wrong_company_header_is_refused(api: httpx.Client, world: World) -> None:  # test 6
    res = api.get("/team", headers={**_bearer(world.env["JWT_A"]), "X-Tenant-Id": world.tenant_b})
    assert res.status_code == 403


def test_normal_user_on_admin_route(api: httpx.Client, world: World) -> None:  # test 7
    assert api.get("/admin/tenants", headers=_bearer(world.env["JWT_A"])).status_code == 403


def test_platform_admin_with_mfa_can_read(api: httpx.Client, world: World) -> None:
    res = api.get(f"/admin/tenants/{world.tenant_b}", headers=_bearer(world.env["JWT_ADMIN"]))
    assert res.status_code == 200 and res.json()["id"] == world.tenant_b
