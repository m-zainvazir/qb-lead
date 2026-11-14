import pytest

from core import net
from core.net import Blocked, check_url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://localhost:6379/",
        "http://127.0.0.1/",
        "http://2130706433/",  # 127.0.0.1 written as a number
        "http://0.0.0.0/",
        "http://10.1.2.3/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://100.64.0.1/",  # shared address space
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[fd00::1]/",
        "file:///etc/passwd",
        "gopher://example.com/",
        "ftp://example.com/",
        "http://user:pw@example.com/",
        "http://example.com:6379/",
        "http://service.internal/",
        "javascript:alert(1)",
    ],
)
def test_internal_and_odd_urls_are_blocked(url: str) -> None:
    with pytest.raises(Blocked):
        check_url(url)


def test_hostname_resolving_to_private_address_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(net, "resolve", lambda host, port: ["93.184.216.34", "10.0.0.5"])
    with pytest.raises(Blocked, match="non-public"):
        check_url("https://rebind.example.com/")


def test_public_hostname_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(net, "resolve", lambda host, port: ["93.184.216.34"])
    assert check_url("https://example.com/page") == ("https", "example.com", 443, "93.184.216.34")


def test_redirect_to_internal_address_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    monkeypatch.setattr(net, "resolve", lambda host, port: ["93.184.216.34"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    real_client = httpx.Client
    monkeypatch.setattr(
        net.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    with pytest.raises(Blocked, match="non-public"):
        net.safe_fetch("http://example.com/start")
