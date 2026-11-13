"""Team settings for the company in X-Tenant-Id. Owners and admins only.

The database enforces the same rules (row-level security); the checks here give clear
403s and stop work early.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from api.auth import CurrentTenant
from api.models import ChangeRole, InvitationOut, Member, Team
from core.db import user_db
from core.features import can

router = APIRouter(prefix="/team", tags=["team"])


@router.get("")
async def get_team(
    ctx: CurrentTenant,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> Team:
    ctx.require_role("owner", "admin")
    if not await can(ctx.tenant_id, "team.view"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not available on your plan")
    async with user_db(ctx.claims) as conn:
        members = await (
            await conn.execute(
                "select * from private.team_members(%s) limit %s offset %s",
                (ctx.tenant_id, limit, offset),
            )
        ).fetchall()
        invitations = await (
            await conn.execute(
                "select id, email::text as email, role, expires_at, created_at"
                " from public.invitations"
                " where tenant_id = %s and accepted_at is null and revoked_at is null"
                "   and expires_at > now()"
                " order by created_at desc limit 100",
                (ctx.tenant_id,),
            )
        ).fetchall()
    return Team(
        members=[Member(**m) for m in members],
        invitations=[InvitationOut(**i) for i in invitations],
    )


@router.patch("/members/{user_id}")
async def change_role(user_id: UUID, body: ChangeRole, ctx: CurrentTenant) -> Member:
    ctx.require_role("owner")  # only an owner changes roles
    if user_id == ctx.auth.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot change your own role")
    async with user_db(ctx.claims) as conn:
        exists = await (
            await conn.execute(
                "select 1 from public.memberships where tenant_id = %s and user_id = %s",
                (ctx.tenant_id, user_id),
            )
        ).fetchone()
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
        # The audit entry is written by a database trigger (same for every path).
        updated = await (
            await conn.execute(
                "update public.memberships set role = %s"
                " where tenant_id = %s and user_id = %s returning user_id",
                (body.role, ctx.tenant_id, user_id),
            )
        ).fetchone()
        if updated is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        member = await (
            await conn.execute(
                "select * from private.team_members(%s) where user_id = %s",
                (ctx.tenant_id, user_id),
            )
        ).fetchone()
    assert member is not None
    return Member(**member)


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(user_id: UUID, ctx: CurrentTenant) -> Response:
    leaving = user_id == ctx.auth.user_id
    if not leaving:
        ctx.require_role("owner")
    async with user_db(ctx.claims) as conn:
        # A database trigger records membership.removed / membership.left.
        removed = await (
            await conn.execute(
                "delete from public.memberships where tenant_id = %s and user_id = %s"
                " returning role",
                (ctx.tenant_id, user_id),
            )
        ).fetchone()
        if removed is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
