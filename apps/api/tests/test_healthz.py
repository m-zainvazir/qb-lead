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
