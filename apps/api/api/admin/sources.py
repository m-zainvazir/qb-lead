"""Temporary sources page API (module 3) until the admin panel arrives in module 9.

Platform admins only (MFA). Changes and cross-company reads are audited. Turning on a
red-risk source needs an explicit override, recorded on the source and in the audit log.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from api.admin.guard import PlatformAdmin
from core.audit import audit_as_system
from core.db import system_db
from core.jobs import enqueue

router = APIRouter(prefix="/admin/sources", tags=["admin"])


class SourceChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    monthly_cap_usd: Decimal | None = Field(default=None, ge=0, le=100000)
    red_override: bool = False


@router.get("")
async def list_sources(admin: PlatformAdmin) -> list[dict[str, Any]]:
    del admin
    async with system_db() as conn:
        rows = await (
            await conn.execute(
                "select s.key, s.name, s.kind, s.risk, s.enabled, s.schedule_seconds,"
                " s.monthly_cap_usd::float as monthly_cap_usd,"
                " s.cost_per_call_usd::float as cost_per_call_usd, s.last_run_at,"
                " s.red_override_at,"
                " coalesce((select sum(u.cost_usd) from public.usage_events u"
                "   where u.source_key = s.key and u.created_at >= date_trunc('month', now())),"
                "   0)::float as spent_this_month,"
                " (select r.status from public.source_runs r where r.source_key = s.key"
                "   order by r.started_at desc limit 1) as last_status,"
                " (select avg(r.cost_usd) from (select cost_usd from public.source_runs"
                "   where source_key = s.key and status = 'succeeded'"
                "   order by started_at desc limit 10) r)::float as avg_run_cost,"
                " (select sum(new_items)::float / nullif(sum(fetched), 0) from (select new_items,"
                "   fetched from public.source_runs where source_key = s.key"
                "   order by started_at desc limit 10) y) as yield"
                " from public.sources s order by s.kind, s.key"
            )
        ).fetchall()
    out = []
    for r in rows:
        runs_per_month = (30 * 86400 / r["schedule_seconds"]) if r["schedule_seconds"] else 0
        out.append(
            {**r, "projected_monthly_usd": round((r["avg_run_cost"] or 0) * runs_per_month, 4)}
        )
    return out


@router.patch("/{key}")
async def change_source(key: str, body: SourceChange, admin: PlatformAdmin) -> dict[str, Any]:
    async with system_db() as conn:
        source = await (
            await conn.execute(
                "select risk, red_override_at from public.sources where key = %s for update",
                (key,),
            )
        ).fetchone()
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown source")
        if body.enabled and source["risk"] == "red" and source["red_override_at"] is None:
            if not body.red_override:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "This source is red-risk: turning it on needs an explicit override",
                )
            await conn.execute(
                "update public.sources set red_override_by = %s, red_override_at = now()"
                " where key = %s",
                (admin.user_id, key),
            )
        if body.enabled is not None:
            await conn.execute(
                "update public.sources set enabled = %s where key = %s", (body.enabled, key)
            )
        if body.monthly_cap_usd is not None:
            await conn.execute(
                "update public.sources set monthly_cap_usd = %s where key = %s",
                (body.monthly_cap_usd, key),
            )
        await audit_as_system(
            conn,
            "admin.source_changed",
            actor_kind="platform_admin",
            actor_user_id=admin.user_id,
            tenant_id=None,
            target_type="source",
            target_id=key,
            metadata=body.model_dump(mode="json", exclude_none=True),
        )
    return {"key": key, "changed": True}


@router.post("/{key}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_now(key: str, admin: PlatformAdmin) -> dict[str, Any]:
    async with system_db() as conn:
        exists = await (
            await conn.execute("select kind from public.sources where key = %s", (key,))
        ).fetchone()
        if exists is None or exists["kind"] != "pull":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or push-only source")
        await audit_as_system(
            conn,
            "admin.source_run_requested",
            actor_kind="platform_admin",
            actor_user_id=admin.user_id,
            tenant_id=None,
            target_type="source",
            target_id=key,
        )
    queued = await enqueue("worker.tasks.run_source", key, "manual")
    return {"key": key, "queued": queued}


@router.get("/runs")
async def recent_runs(
    admin: PlatformAdmin, limit: Annotated[int, Query(ge=1, le=100)] = 30
) -> list[dict[str, Any]]:
    del admin
    async with system_db() as conn:
        rows = await (
            await conn.execute(
                "select id, source_key, status, trigger, queries, fetched, new_items,"
                " cost_usd::float as cost_usd, error, started_at, finished_at"
                " from public.source_runs order by started_at desc limit %s",
                (limit,),
            )
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/items")
async def recent_items(
    admin: PlatformAdmin,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    source: Annotated[str | None, Query(max_length=40)] = None,
) -> list[dict[str, Any]]:
    async with system_db() as conn:
        rows = await (
            await conn.execute(
                "select id, source_key, visibility, tenant_id, title, left(body, 400) as body,"
                " url, author_handle, posted_at, fetched_at from public.raw_items"
                " where (%s::text is null or source_key = %s)"
                " order by fetched_at desc limit %s",
                (source, source, limit),
            )
        ).fetchall()
        await audit_as_system(
            conn,
            "admin.raw_items_listed",
            actor_kind="platform_admin",
            actor_user_id=admin.user_id,
            tenant_id=None,
            metadata={"limit": limit, "source": source, "count": len(rows)},
        )
    return [dict(r) for r in rows]
