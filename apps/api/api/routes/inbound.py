"""A company's inbound addresses (webhook URL, email address) and its private items."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict

from api.auth import CurrentTenant
from core.db import user_db
from core.settings import get_settings

router = APIRouter(prefix="/inbound", tags=["inbound"])


class NewEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["webhook", "email"]


class PrivateItem(BaseModel):
    id: UUID
    source_key: str
    title: str | None
    body: str | None
    url: str | None
    author_handle: str | None
    fetched_at: datetime


@router.get("")
async def inbound_overview(ctx: CurrentTenant) -> dict[str, Any]:
    async with user_db(ctx.claims) as conn:
        endpoints = (
            await (
                await conn.execute(
                    "select id, kind, token_hint, email_local, created_at, revoked_at"
                    " from public.inbound_endpoints where tenant_id = %s and revoked_at is null"
                    " order by created_at desc",
                    (ctx.tenant_id,),
                )
            ).fetchall()
            if ctx.role in ("owner", "admin")
            else []
        )
        items = await (
            await conn.execute(
                "select id, source_key, title, body, url, author_handle, fetched_at"
                " from public.raw_items where tenant_id = %s and visibility = 'private'"
                " order by fetched_at desc limit 50",
                (ctx.tenant_id,),
            )
        ).fetchall()
    domain = get_settings().inbound_email_domain
    return {
        "endpoints": [
            {**e, "email": f"{e['email_local']}@{domain}" if e["email_local"] else None}
            for e in endpoints
        ],
        "items": [PrivateItem(**i) for i in items],
    }


@router.post("/endpoints", status_code=status.HTTP_201_CREATED)
async def create_endpoint(body: NewEndpoint, ctx: CurrentTenant) -> dict[str, Any]:
    ctx.require_role("owner", "admin")
    token = secrets.token_urlsafe(32)
    email_local = f"in-{secrets.token_hex(6)}" if body.kind == "email" else None
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute(
                "select private.create_inbound_endpoint(%s, %s, %s, %s, %s) as id",
                (
                    ctx.tenant_id,
                    body.kind,
                    hashlib.sha256(token.encode()).hexdigest(),
                    token[:6],
                    email_local,
                ),
            )
        ).fetchone()
    assert row is not None
    out: dict[str, Any] = {"id": row["id"], "kind": body.kind}
    if body.kind == "webhook":
        out["token"] = token  # shown once; only its hash is stored
        out["path"] = f"/ingest/{token}"
    else:
        out["email"] = f"{email_local}@{get_settings().inbound_email_domain}"
    return out


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_endpoint(endpoint_id: UUID, ctx: CurrentTenant) -> Response:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute(
                "select private.revoke_inbound_endpoint(%s) as tenant_id", (endpoint_id,)
            )
        ).fetchone()
    if row is None or row["tenant_id"] != ctx.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", status_code=status.HTTP_201_CREATED)
async def send_test(ctx: CurrentTenant) -> dict[str, Any]:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute("select private.send_test_item(%s) as id", (ctx.tenant_id,))
        ).fetchone()
    return {"raw_item_id": row["id"] if row else None}
