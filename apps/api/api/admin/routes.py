"""Admin routes. Every cross-company read writes an audit entry in the same transaction,
so a read without its log entry cannot happen."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from api.admin.guard import PlatformAdmin
from core.audit import audit_as_system
from core.db import system_db

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminTenant(BaseModel):
    id: UUID
    name: str
    type: Literal["freelancer", "agency"]
    status: Literal["active", "suspended", "deleted"]
    is_internal: bool
    created_at: datetime
    member_count: int


class AdminMember(BaseModel):
    user_id: UUID
    email: str
    role: Literal["owner", "admin", "member"]
    joined_at: datetime
    last_sign_in_at: datetime | None


class AdminTenantDetail(AdminTenant):
    members: list[AdminMember]


class AdminTenantList(BaseModel):
    items: list[AdminTenant]
    limit: int
    offset: int


@router.get("/tenants")
async def list_tenants(
    admin: PlatformAdmin,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> AdminTenantList:
    async with system_db() as conn:
        rows = await (
            await conn.execute(
                "select t.id, t.name, t.type, t.status, t.is_internal, t.created_at,"
                " (select count(*) from public.memberships m where m.tenant_id = t.id)::int"
                " as member_count from public.tenants t"
                " order by t.created_at desc, t.id limit %s offset %s",
                (limit, offset),
            )
        ).fetchall()
        await audit_as_system(
            conn,
            "admin.tenants_listed",
            actor_kind="platform_admin",
            actor_user_id=admin.user_id,
            tenant_id=None,
            metadata={"limit": limit, "offset": offset, "count": len(rows)},
        )
    return AdminTenantList(items=[AdminTenant(**r) for r in rows], limit=limit, offset=offset)


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: UUID, admin: PlatformAdmin) -> AdminTenantDetail:
    async with system_db() as conn:
        row = await (
            await conn.execute(
                "select t.id, t.name, t.type, t.status, t.is_internal, t.created_at,"
                " (select count(*) from public.memberships m where m.tenant_id = t.id)::int"
                " as member_count from public.tenants t"
                " where t.id = %s",
                (tenant_id,),
            )
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
        members = await (
            await conn.execute("select * from private.admin_tenant_members(%s)", (tenant_id,))
        ).fetchall()
        await audit_as_system(
            conn,
            "admin.tenant_viewed",
            actor_kind="platform_admin",
            actor_user_id=admin.user_id,
            tenant_id=tenant_id,
            target_type="tenant",
            target_id=tenant_id,
        )
    return AdminTenantDetail(**row, members=[AdminMember(**m) for m in members])
