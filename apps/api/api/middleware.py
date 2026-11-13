"""Request id and access logging."""

from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

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
