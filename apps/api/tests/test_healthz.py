from fastapi.testclient import TestClient

from api.main import create_app


def test_healthz_reports_status_and_commit() -> None:
    client = TestClient(create_app(with_db=False))
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "commit": "testsha"}
    assert res.headers["X-Request-Id"]


def test_request_id_is_echoed_when_safe() -> None:
    client = TestClient(create_app(with_db=False))
    res = client.get("/healthz", headers={"X-Request-Id": "abc12345-req"})
    assert res.headers["X-Request-Id"] == "abc12345-req"


def test_unsafe_request_id_is_replaced() -> None:
    client = TestClient(create_app(with_db=False))
    res = client.get("/healthz", headers={"X-Request-Id": "bad id\nwith newline"})
    assert res.headers["X-Request-Id"] != "bad id\nwith newline"


def test_oversized_body_is_refused() -> None:
    client = TestClient(create_app(with_db=False))
    res = client.post(
        "/me", content=b"x" * (600 * 1024), headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 413


async def test_validation_errors_do_not_echo_input() -> None:
    from fastapi.exceptions import RequestValidationError

    from api.errors import _validation

    exc = RequestValidationError(
        [{"type": "string_too_long", "loc": ("body", "tone"), "msg": "too long", "input": "SECRET"}]
    )
    res = await _validation(None, exc)  # type: ignore[arg-type]
    assert res.status_code == 422
    assert b"SECRET" not in res.body
    assert b"string_too_long" in res.body
