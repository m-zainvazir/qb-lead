"""Catalogue administration: add services, markets, signal types and questions as data.

Platform admins only (MFA). Writes go through system_db (catalogue tables are not
writable by users) and every change writes an audit entry.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from api.admin.guard import PlatformAdmin
from core.audit import audit_as_system
from core.db import Conn, system_db

router = APIRouter(prefix="/admin/catalogue", tags=["admin"])

Text = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]
Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,59}$")]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,50}$")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProblemIn(Input):
    label: Text
    phrases: list[Text] = Field(default_factory=list, max_length=30)


class ServiceIn(Input):
    slug: Slug
    name: Text
    description: str = Field(default="", max_length=2000)
    problems: list[ProblemIn] = Field(default_factory=list, max_length=30)
    technologies: list[Slug] = Field(default_factory=list, max_length=30)
    sort_order: int = Field(default=100, ge=0, le=10000)


class MarketIn(Input):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
    name: Text
    default_weight: float = Field(default=0.7, ge=0, le=1)
    sort_order: int = Field(default=100, ge=0, le=10000)


class SignalIn(Input):
    key: Key
    label: Text
    description: str = Field(default="", max_length=1000)
    temperature: Literal["hot", "warm"]
    default_weight: float = Field(default=0.7, ge=0, le=1)
    sort_order: int = Field(default=100, ge=0, le=10000)


class QuestionIn(Input):
    key: Key
    step: int = Field(ge=1, le=20)
    sort_order: int = Field(default=100, ge=0, le=10000)
    type: Literal[
        "single_choice",
        "multi_choice",
        "number",
        "text",
        "long_text",
        "catalogue_services",
        "catalogue_markets",
        "catalogue_signals",
    ]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    help: str = Field(default="", max_length=1000)
    options: list[dict[str, str]] = Field(default_factory=list, max_length=30)
    required: bool = True
    validation: dict[str, int] = Field(default_factory=dict, max_length=10)
    show_if: dict[str, str] | None = None
    maps_to: Literal[
        "profile.type",
        "profile.team_size",
        "profile.min_budget_usd",
        "profile.client_sizes",
        "profile.tone",
        "profile.priorities",
        "profile.time_zone",
        "profile.about",
        "services",
        "custom_services",
        "markets",
        "signals",
        "exclusions",
    ]


class ActiveIn(Input):
    is_active: bool


Kind = Literal["services", "markets", "signal_types", "onboarding_questions", "sample_posts"]


async def _audit(
    conn: Conn, admin: Any, action: str, kind: str, target: Any, meta: dict[str, Any]
) -> None:
    await audit_as_system(
        conn,
        action,
        actor_kind="platform_admin",
        actor_user_id=admin.user_id,
        tenant_id=None,
        target_type=kind,
        target_id=str(target),
        metadata=meta,
    )


@router.get("")
async def get_catalogue(admin: PlatformAdmin) -> dict[str, Any]:
    del admin
    async with system_db() as conn:
        out: dict[str, Any] = {}
        out["services"] = await (
            await conn.execute(
                "select id, slug, name, description, is_active, sort_order,"
                " (select count(*) from public.problems p where p.service_id = s.id)::int"
                " as problems"
                " from public.services s order by sort_order, name"
            )
        ).fetchall()
        out["markets"] = await (
            await conn.execute(
                "select id, code, name, default_weight::float, is_active, sort_order"
                " from public.markets order by sort_order"
            )
        ).fetchall()
        out["signal_types"] = await (
            await conn.execute(
                "select id, key, label, temperature, default_weight::float, is_active, sort_order"
                " from public.signal_types order by sort_order"
            )
        ).fetchall()
        out["onboarding_questions"] = await (
            await conn.execute(
                "select id, key, step, type, label, maps_to, required, is_active"
                " from public.onboarding_questions order by step, sort_order"
            )
        ).fetchall()
    return out


@router.post("/services", status_code=status.HTTP_201_CREATED)
async def add_service(body: ServiceIn, admin: PlatformAdmin) -> dict[str, Any]:
    async with system_db() as conn:
        row = await (
            await conn.execute(
                "insert into public.services (slug, name, description, sort_order)"
                " values (%s, %s, %s, %s) returning id",
                (body.slug, body.name, body.description, body.sort_order),
            )
        ).fetchone()
        assert row is not None
        for i, problem in enumerate(body.problems):
            await conn.execute(
                "insert into public.problems (service_id, label, example_phrases, sort_order)"
                " values (%s, %s, %s, %s)",
                (row["id"], problem.label, list(problem.phrases), (i + 1) * 10),
            )
        if body.technologies:
            await conn.execute(
                "insert into public.service_technologies (service_id, technology_id)"
                " select %s, t.id from public.technologies t where t.slug = any(%s)"
                " on conflict do nothing",
                (row["id"], list(body.technologies)),
            )
        await _audit(
            conn, admin, "admin.catalogue_added", "service", row["id"], {"slug": body.slug}
        )
    return {"id": row["id"]}


@router.post("/markets", status_code=status.HTTP_201_CREATED)
async def add_market(body: MarketIn, admin: PlatformAdmin) -> dict[str, Any]:
    async with system_db() as conn:
        row = await (
            await conn.execute(
                "insert into public.markets (code, name, default_weight, sort_order)"
                " values (%s, %s, %s, %s) returning id",
                (body.code, body.name, body.default_weight, body.sort_order),
            )
        ).fetchone()
        assert row is not None
        await _audit(conn, admin, "admin.catalogue_added", "market", row["id"], {"code": body.code})
    return {"id": row["id"]}


@router.post("/signal_types", status_code=status.HTTP_201_CREATED)
async def add_signal(body: SignalIn, admin: PlatformAdmin) -> dict[str, Any]:
    async with system_db() as conn:
        row = await (
            await conn.execute(
                "insert into public.signal_types"
                " (key, label, description, temperature, default_weight, sort_order)"
                " values (%s, %s, %s, %s, %s, %s) returning id",
                (
                    body.key,
                    body.label,
                    body.description,
                    body.temperature,
                    body.default_weight,
                    body.sort_order,
                ),
            )
        ).fetchone()
        assert row is not None
        await _audit(
            conn, admin, "admin.catalogue_added", "signal_type", row["id"], {"key": body.key}
        )
    return {"id": row["id"]}


@router.post("/onboarding_questions", status_code=status.HTTP_201_CREATED)
async def add_question(body: QuestionIn, admin: PlatformAdmin) -> dict[str, Any]:
    async with system_db() as conn:
        row = await (
            await conn.execute(
                "insert into public.onboarding_questions (key, step, sort_order, type, label, help,"
                " options, required, validation, show_if, maps_to)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
                (
                    body.key,
                    body.step,
                    body.sort_order,
                    body.type,
                    body.label,
                    body.help,
                    Jsonb(body.options),
                    body.required,
                    Jsonb(body.validation),
                    Jsonb(body.show_if) if body.show_if else None,
                    body.maps_to,
                ),
            )
        ).fetchone()
        assert row is not None
        await _audit(
            conn,
            admin,
            "admin.catalogue_added",
            "onboarding_question",
            row["id"],
            {"key": body.key},
        )
    return {"id": row["id"]}


# Fixed statements per kind (no table names built from input).
_SET_ACTIVE: dict[str, str] = {
    "services": "update public.services set is_active = %s where id = %s returning id",
    "markets": "update public.markets set is_active = %s where id = %s returning id",
    "signal_types": "update public.signal_types set is_active = %s where id = %s returning id",
    "onboarding_questions": (
        "update public.onboarding_questions set is_active = %s where id = %s returning id"
    ),
    "sample_posts": "update public.sample_posts set is_active = %s where id = %s returning id",
}


@router.patch("/{kind}/{item_id}")
async def set_active(
    kind: Kind, item_id: UUID, body: ActiveIn, admin: PlatformAdmin
) -> dict[str, Any]:
    async with system_db() as conn:
        row = await (await conn.execute(_SET_ACTIVE[kind], (body.is_active, item_id))).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        await _audit(
            conn, admin, "admin.catalogue_changed", kind, item_id, {"is_active": body.is_active}
        )
    return {"id": item_id, "is_active": body.is_active}
