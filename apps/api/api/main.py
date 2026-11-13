"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import errors
from api.admin import routes as admin_routes
from api.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from api.routes import invitations, me, onboarding, portfolio, profile, team, tenants
from core import db
from core.logging import configure_logging
from core.settings import get_settings

# The only routes reachable without a login. Anything else answers 401 without a valid
# token (apps/api/tests/test_public_routes.py checks every route).
PUBLIC_ROUTES: frozenset[str] = frozenset({"/healthz"})


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
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    errors.install(app)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "commit": settings.git_commit}

    app.include_router(me.router)
    app.include_router(tenants.router)
    app.include_router(team.router)
    app.include_router(invitations.router)
    app.include_router(onboarding.router)
    app.include_router(profile.router)
    app.include_router(portfolio.router)
    app.include_router(admin_routes.router)

    return app
