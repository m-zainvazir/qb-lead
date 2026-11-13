"""Invitations: single-use, random, tied to one email, expire after 7 days.

Only the SHA-256 of the token is stored. The raw token exists in the email link and,
if the email could not be sent, in the response to the inviter.
"""

from __future__ import annotations

import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from api.auth import CurrentTenant, CurrentUser
from api.models import (
    AcceptedInvitation,
    CreateInvitation,
    InvitationOut,
    InvitationPreview,
    InvitationToken,
)
from core.db import user_db
from core.features import can
from core.mailer import Email, get_mailer
from core.settings import get_settings

router = APIRouter(prefix="/invitations", tags=["invitations"])


class CreatedInvitation(BaseModel):
    invitation: InvitationOut
    email_sent: bool
    invite_url: str | None  # only when the email could not be sent


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_invitation(body: CreateInvitation, ctx: CurrentTenant) -> CreatedInvitation:
    ctx.require_role("owner", "admin")
    if body.role == "admin":
        ctx.require_role("owner")  # only an owner hands out the admin role
    if not await can(ctx.tenant_id, "team.invite"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not available on your plan")

    token = secrets.token_urlsafe(32)
    email = str(body.email).lower()
    # The database enforces the daily cap, "already a member" and one open invitation per
    # email (also for direct REST calls), and a trigger writes the audit entry.
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute(
                "insert into public.invitations (tenant_id, email, role, token_hash)"
                " values (%s, %s, %s, %s)"
                " returning id, email::text as email, role, expires_at, created_at",
                (ctx.tenant_id, email, body.role, hash_token(token)),
            )
        ).fetchone()
        assert row is not None
        company = await (
            await conn.execute("select name from public.tenants where id = %s", (ctx.tenant_id,))
        ).fetchone()

    url = f"{get_settings().web_base_url.rstrip('/')}/invite/{token}"
    company_name = company["name"] if company else "a company"
    sent = await get_mailer().send(
        Email(
            to=email,
            subject=f"You are invited to join {company_name}",
            text=(
                f"You have been invited to join {company_name} as {body.role}.\n\n"
                f"Accept the invitation here (it works once and expires in 7 days):\n{url}\n\n"
                "Sign in or sign up with this email address to accept.\n"
                "If you did not expect this, you can ignore this email."
            ),
        )
    )
    return CreatedInvitation(
        invitation=InvitationOut(**row), email_sent=sent, invite_url=None if sent else url
    )


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(invitation_id: UUID, ctx: CurrentTenant) -> Response:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute(
                "select private.revoke_invitation(%s) as tenant_id", (invitation_id,)
            )
        ).fetchone()
        if row is None or row["tenant_id"] != ctx.tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/preview")
async def preview_invitation(body: InvitationToken, user: CurrentUser) -> InvitationPreview:
    async with user_db(user.claims) as conn:
        row = await (
            await conn.execute("select * from private.preview_invitation(%s)", (body.token,))
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found or no longer valid")
    return InvitationPreview(
        company_name=row["tenant_name"],
        role=row["role"],
        email=row["email"],
        is_valid=row["is_valid"],
    )


@router.post("/accept")
async def accept_invitation(body: InvitationToken, user: CurrentUser) -> AcceptedInvitation:
    # Single use, email match, expiry and the audit entry are all enforced in
    # private.accept_invitation, under a row lock.
    async with user_db(user.claims) as conn:
        row = await (
            await conn.execute("select private.accept_invitation(%s) as tenant_id", (body.token,))
        ).fetchone()
    assert row is not None
    return AcceptedInvitation(tenant_id=row["tenant_id"])
