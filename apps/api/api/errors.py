"""Turn database errors into safe HTTP responses.

Messages never include SQL, constraint names or other internals. The request id is
returned so a user report can be matched to the logs.
"""

from __future__ import annotations

import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.logging import request_id_var

log = logging.getLogger(__name__)

# SQLSTATE -> (HTTP status, message shown to the caller)
_MAP: dict[str, tuple[int, str]] = {
    "28000": (401, "Not authenticated"),
    "42501": (403, "Not allowed"),
    "LG403": (403, "Not allowed"),
    "LG404": (404, "Not found or no longer valid"),
    "LG409": (409, "That conflicts with the current state"),
    "LG429": (429, "Limit reached; try again later"),
    "LG400": (400, "Invalid request"),
    "23505": (409, "That already exists"),
    "23503": (409, "That refers to something that does not exist"),
    "23514": (422, "A value is not allowed"),
    "23502": (422, "A required value is missing"),
    "22P02": (422, "A value has the wrong format"),
    "22001": (422, "A value is too long"),
}


def _body(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"detail": message, "request_id": request_id_var.get()},
    )


async def _db_error(_request: Request, exc: Exception) -> JSONResponse:
    sqlstate = getattr(exc, "sqlstate", None) or ""
    status, message = _MAP.get(sqlstate, (500, "Something went wrong"))
    if (
        sqlstate in ("LG409", "LG429")
        and isinstance(exc, psycopg.Error)
        and exc.diag.message_primary
    ):
        # Our own LG4xx messages are written for users ("a company must keep at least one owner").
        message = exc.diag.message_primary
    level = logging.ERROR if status >= 500 else logging.INFO
    log.log(
        level, "db_error", extra={"sqlstate": sqlstate, "status": status}, exc_info=status >= 500
    )
    return _body(status, message)


async def _validation(_request: Request, exc: Exception) -> JSONResponse:
    # Never echo the submitted values back (they can be huge, or contain secrets).
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    detail = [
        {"type": e.get("type"), "loc": list(e.get("loc", ())), "msg": e.get("msg")}
        for e in errors[:20]
    ]
    return JSONResponse(
        status_code=422, content={"detail": detail, "request_id": request_id_var.get()}
    )


async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error", exc_info=exc)
    return _body(500, "Something went wrong")


def install(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(psycopg.Error, _db_error)
    app.add_exception_handler(Exception, _unhandled)
