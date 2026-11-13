from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from api.auth import current_user
from core.db import system_db


@dataclass(frozen=True)
class AdminContext:
    user_id: UUID
    email: str
    level: Literal["super", "support"]
    claims: dict[str, Any]


async def require_platform_admin(request: Request) -> AdminContext:
    # current_user verifies the token and that the session is still active.
    user = await current_user(request)
    async with system_db() as conn:
        row = await (
            await conn.execute(
                "select level from public.platform_admins where user_id = %s", (user.user_id,)
            )
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admins only")
    if user.aal != "aal2":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Verify with your authenticator app first (MFA required)"
        )
    return AdminContext(
        user_id=user.user_id, email=user.email, level=row["level"], claims=user.claims
    )


PlatformAdmin = Annotated[AdminContext, Depends(require_platform_admin)]
