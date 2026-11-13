"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.middleware import RequestIdMiddleware
from core import db
from core.logging import configure_logging
from core.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await db.open_pools()
    try:
        yield
    finally:
        await db.close_pools()


def create_app(*, with_db: bool = True) -> FastAPI:
    settings = get_settings()  # fails here, at startup, if a required value is missing
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Lead Generation API",
        version="0.1.0",
        lifespan=lifespan if with_db else None,
        # The interactive docs are off outside local development.
        docs_url="/docs" if settings.app_env == "local" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env in ("local", "test") else None,
    )
    app.add_middleware(RequestIdMiddleware)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "commit": settings.git_commit}

    return app
