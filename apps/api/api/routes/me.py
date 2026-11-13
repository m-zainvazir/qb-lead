from __future__ import annotations

from fastapi import APIRouter

from api.auth import CurrentUser
from api.models import Company, Me, PlatformAdminInfo
from core.db import user_db

router = APIRouter(tags=["me"])


@router.get("/me")
async def get_me(user: CurrentUser) -> Me:
    async with user_db(user.claims) as conn:
        companies = await (
            await conn.execute(
                "select t.id, t.name, t.type, m.role, t.is_internal"
                " from public.memberships m join public.tenants t on t.id = m.tenant_id"
                " where m.user_id = auth.uid()"
                " order by t.name, t.id"
                " limit 100"
            )
        ).fetchall()
        admin = await (
            await conn.execute(
                "select level from public.platform_admins where user_id = auth.uid()"
            )
        ).fetchone()
    return Me(
        id=user.user_id,
        email=user.email,
        companies=[Company(**row) for row in companies],
        platform_admin=PlatformAdminInfo(level=admin["level"], mfa_verified=user.aal == "aal2")
        if admin
        else None,
    )
