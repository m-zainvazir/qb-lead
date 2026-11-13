"""Request id and access logging."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from core.logging import request_id_var

log = logging.getLogger("api.access")

# Accept a caller-supplied id only if it is short and plain; otherwise make our own.
_SAFE_ID = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.state.request_id = rid
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = rid
            return response
        finally:
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Refuse oversized request bodies with 413 before anything parses them.

    Uploads (paths in `upload_paths`) get `max_upload` bytes, everything else `max_body`.
    Counts the actual stream, so a missing or false Content-Length does not help.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body: int = 512 * 1024,
        max_upload: int = 11 * 1024 * 1024,
        upload_paths: tuple[str, ...] = ("/portfolio",),
    ) -> None:
        self.app = app
        self.max_body = max_body
        self.max_upload = max_upload
        self.upload_paths = upload_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        limit = self.max_upload if path.startswith(self.upload_paths) else self.max_body
        declared = dict(scope.get("headers", [])).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _too_large(send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _too_large(send)


class _BodyTooLarge(Exception):
    pass


async def _too_large(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": b'{"detail":"Request body too large"}'})
