"""Guarded fetcher for links taken from outside content (SSRF protection).

Every URL that came from a post, email or webhook is fetched only through `safe_fetch`:

* schemes: http and https only; no user:password@ in the URL; ports 80/443/8080/8443
* the host is resolved first and EVERY address must be public (no loopback, private,
  link-local incl. 169.254.169.254, shared 100.64/10, multicast, reserved, unspecified)
* the connection goes to the vetted IP (Host header and TLS SNI keep the real name), so a
  DNS answer cannot change between the check and the connection (rebinding)
* redirects are followed by hand, at most 3, and every hop is checked again
* size and content-type limits; short timeouts
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

ALLOWED_PORTS = {80, 443, 8080, 8443}
MAX_REDIRECTS = 3
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
ALLOWED_TYPES = ("text/html", "text/plain", "application/xhtml+xml")


class Blocked(Exception):
    """The URL is not allowed (reason in the message)."""


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    content_type: str
    text: str


def _public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def resolve(host: str, port: int) -> list[str]:
    """All addresses for a host (overridable in tests)."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


def check_url(url: str) -> tuple[str, str, int, str]:
    """Validate a URL and return (scheme, host, port, vetted_ip). Raises Blocked."""
    try:
        parts = urlsplit(url.strip())
    except ValueError as exc:
        raise Blocked("not a valid URL") from exc
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise Blocked(f"scheme {scheme or '(none)'} is not allowed")
    if parts.username or parts.password:
        raise Blocked("credentials in URLs are not allowed")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise Blocked("no host")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise Blocked("bad port") from exc
    if port not in ALLOWED_PORTS:
        raise Blocked(f"port {port} is not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise Blocked(f"host {host} is internal")
        try:
            addresses = resolve(host, port)
        except OSError as exc:
            raise Blocked(f"cannot resolve {host}") from exc
    if not addresses:
        raise Blocked(f"cannot resolve {host}")
    for address in addresses:
        if not _public(ipaddress.ip_address(address.split("%")[0])):
            raise Blocked(f"{host} resolves to a non-public address ({address})")
    return scheme, host, port, addresses[0]


def safe_fetch(url: str) -> Fetched:
    current = url
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port, ip = check_url(current)
            parts = urlsplit(current)
            ip_host = f"[{ip}]" if ":" in ip else ip
            target = urlunsplit((scheme, f"{ip_host}:{port}", parts.path or "/", parts.query, ""))
            request = client.build_request(
                "GET",
                target,
                headers={
                    "Host": host if port in (80, 443) else f"{host}:{port}",
                    "User-Agent": "leadgen-fetcher/1.0",
                    "Accept": "text/html,text/plain",
                },
                extensions={"sni_hostname": host},
            )
            response = client.send(request, stream=True)
            try:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    if not location:
                        raise Blocked("redirect without a location")
                    current = urljoin(current, location)
                    continue
                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                if content_type not in ALLOWED_TYPES:
                    raise Blocked(f"content type {content_type or '(none)'} is not fetched")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise Blocked("response is too large")
                return Fetched(
                    url=current,
                    status=response.status_code,
                    content_type=content_type,
                    text=body.decode(response.encoding or "utf-8", errors="replace"),
                )
            finally:
                response.close()
    raise Blocked("too many redirects")
