"""The onboarding wizard: questions as data, resumable progress, completion."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from api.auth import CurrentTenant
from api.profiles import answers_to_input, save_profile
from core.db import Conn, user_db
from core.jobs import enqueue

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

MAX_ANSWER_CHARS = 4000  # any single answer; per-question limits are stricter


class Progress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: int = Field(ge=1, le=20)
    answers: dict[str, Any] = Field(max_length=50)


class Onboarding(BaseModel):
    questions: list[dict[str, Any]]
    options: dict[str, list[dict[str, Any]]]
    progress: dict[str, Any] | None
    steps: int


async def _questions(conn: Conn) -> list[dict[str, Any]]:
    rows = await (
        await conn.execute(
            "select key, step, type, label, help, options, required, validation, show_if, maps_to"
            " from public.onboarding_questions order by step, sort_order, key"
        )
    ).fetchall()
    return [dict(r) for r in rows]


def _check_answers(answers: dict[str, Any], questions: list[dict[str, Any]]) -> None:
    known = {q["key"]: q for q in questions}
    for key, value in answers.items():
        if key not in known:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown question {key!r}")
        limit = int(known[key]["validation"].get("max_length", MAX_ANSWER_CHARS))
        items = value if isinstance(value, list) else [value]
        if len(items) > 50:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Too many values for {key}")
        for item in items:
            if not isinstance(item, (str, int, float, bool)) or item is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Bad value for {key}")
            if isinstance(item, str) and len(item) > limit:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"Answer to {key} is too long"
                )


@router.get("")
async def get_onboarding(ctx: CurrentTenant) -> Onboarding:
    async with user_db(ctx.claims) as conn:
        questions = await _questions(conn)
        services = await (
            await conn.execute(
                "select id, name as label, description from public.services"
                " order by sort_order, name"
            )
        ).fetchall()
        markets = await (
            await conn.execute(
                "select id, name as label, code from public.markets order by sort_order"
            )
        ).fetchall()
        signals = await (
            await conn.execute(
                "select id, label, description, temperature from public.signal_types"
                " order by sort_order"
            )
        ).fetchall()
        progress = await (
            await conn.execute(
                "select current_step, answers, completed_at from public.onboarding_progress"
                " where tenant_id = %s",
                (ctx.tenant_id,),
            )
        ).fetchone()
    return Onboarding(
        questions=questions,
        options={
            "catalogue_services": [dict(r) for r in services],
            "catalogue_markets": [dict(r) for r in markets],
            "catalogue_signals": [dict(r) for r in signals],
        },
        progress=dict(progress) if progress else None,
        steps=max((q["step"] for q in questions), default=0),
    )


@router.put("/progress")
async def save_progress(body: Progress, ctx: CurrentTenant) -> dict[str, Any]:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        _check_answers(body.answers, await _questions(conn))
        await conn.execute(
            "insert into public.onboarding_progress (tenant_id, current_step, answers)"
            " values (%s, %s, %s) on conflict (tenant_id) do update"
            " set current_step = excluded.current_step, answers = excluded.answers",
            (ctx.tenant_id, body.current_step, Jsonb(body.answers)),
        )
    return {"saved": True, "current_step": body.current_step}


@router.post("/complete")
async def complete_onboarding(ctx: CurrentTenant) -> dict[str, Any]:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        questions = await _questions(conn)
        progress = await (
            await conn.execute(
                "select answers from public.onboarding_progress where tenant_id = %s",
                (ctx.tenant_id,),
            )
        ).fetchone()
        if progress is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Answer the questions first")
        data = answers_to_input(progress["answers"], questions)
        version = await save_profile(conn, ctx.tenant_id, data)
        await conn.execute(
            "update public.onboarding_progress set completed_at = now() where tenant_id = %s",
            (ctx.tenant_id,),
        )
    queued = await enqueue("worker.tasks.compile_profile", str(ctx.tenant_id))
    return {"version": version, "compile_queued": queued}
