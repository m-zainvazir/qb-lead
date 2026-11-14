"""Every route needs a login unless it is on the short written list of public routes."""

from __future__ import annotations

import re
import uuid

import pytest
from fastapi.testclient import TestClient

from api.main import PUBLIC_ROUTES, create_app

app = create_app(with_db=False)
client = TestClient(app, raise_server_exceptions=False)
# The OpenAPI schema lists every route, including those in included routers.
ROUTES = [
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    for method in sorted(operations)
]


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


def test_routes_were_discovered() -> None:
    assert ("GET", "/me") in ROUTES


def test_public_list_is_short() -> None:
    assert {"/healthz", "/ingest/{token}", "/inbound/email"} == PUBLIC_ROUTES


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if r[1] not in PUBLIC_ROUTES])
def test_route_requires_login(method: str, path: str) -> None:
    res = client.request(method, _concrete(path), json={})
    assert res.status_code == 401, f"{method} {path} answered {res.status_code} without a token"


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if r[1] not in PUBLIC_ROUTES])
def test_route_rejects_garbage_token(method: str, path: str) -> None:
    res = client.request(
        method, _concrete(path), json={}, headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert res.status_code == 401
