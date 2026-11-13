"""The profile editor: read the compiled profile, save changes (recompiled in the background)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from api.auth import CurrentTenant
from api.profiles import ProfileInput, load_profile, save_profile
from core.db import user_db
from core.jobs import enqueue

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(ctx: CurrentTenant) -> dict[str, Any]:
    async with user_db(ctx.claims) as conn:
        profile = await load_profile(conn, ctx.tenant_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile yet: finish onboarding first")
    return profile


@router.put("")
async def put_profile(body: ProfileInput, ctx: CurrentTenant) -> dict[str, Any]:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        version = await save_profile(conn, ctx.tenant_id, body)
    queued = await enqueue("worker.tasks.compile_profile", str(ctx.tenant_id))
    return {"version": version, "compile_status": "pending", "compile_queued": queued}
