"""The company profile: validated input, answers -> named fields, and saving.

Answers from the questionnaire map to named fields through each question's `maps_to`.
Nothing later re-reads free text to guess meaning: the pipeline reads these fields.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from core.db import Conn

Short = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]
ServiceName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$"
    ),
]


class ProfileInput(BaseModel):
    """Everything the onboarding wizard and the profile editor can set. Unknown fields fail."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["freelancer", "agency"]
    team_size: int | None = Field(default=None, ge=1, le=5000)
    min_budget_usd: int = Field(ge=0, le=10_000_000)
    client_sizes: list[Literal["solo", "small", "mid", "enterprise"]] = Field(
        min_length=1, max_length=4
    )
    tone: Literal["friendly", "professional", "direct"]
    priorities: list[Literal["speed", "quality", "price", "long_term"]] = Field(
        min_length=1, max_length=3
    )
    time_zone: str = Field(max_length=64, pattern=r"^[A-Za-z_]+(/[A-Za-z_+-]+){0,2}$")
    about: str | None = Field(default=None, max_length=2000)
    services: list[UUID] = Field(default_factory=list, max_length=10)
    custom_services: list[ServiceName] = Field(default_factory=list, max_length=5)
    markets: list[UUID] = Field(min_length=1, max_length=20)
    signals: list[UUID] = Field(min_length=1, max_length=20)
    exclusions: list[Short] = Field(default_factory=list, max_length=50)


def answers_to_input(answers: dict[str, Any], questions: list[dict[str, Any]]) -> ProfileInput:
    """Map wizard answers (keyed by question key) onto named profile fields."""
    fields: dict[str, Any] = {}
    for q in questions:
        if q["key"] not in answers:
            continue
        value = answers[q["key"]]
        target = q["maps_to"].removeprefix("profile.")
        if target == "custom_services" and isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if target == "exclusions" and isinstance(value, str):
            value = [v.strip() for v in value.splitlines() if v.strip()]
        if value in ("", None) and not q["required"]:
            continue
        fields[target] = value
    if fields.get("type") == "freelancer":
        fields.pop("team_size", None)
    try:
        return ProfileInput.model_validate(fields)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()],
        ) from exc


async def save_profile(conn: Conn, tenant_id: UUID, data: ProfileInput) -> int:
    """Write the profile and its sets in one transaction; returns the new version.

    Row-level security decides whether the caller may write; triggers bump the version
    once for the whole save and write the audit trail.
    """
    if not data.services and not data.custom_services:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose at least one service")
    await _check_catalogue(conn, "services", data.services)
    await _check_catalogue(conn, "markets", data.markets)
    await _check_catalogue(conn, "signal_types", data.signals)

    await conn.execute(
        "insert into public.tenant_profiles (tenant_id, type, team_size, min_budget_usd,"
        " client_sizes, tone, priorities, time_zone, about)"
        " values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " on conflict (tenant_id) do update set type = excluded.type,"
        " team_size = excluded.team_size, min_budget_usd = excluded.min_budget_usd,"
        " client_sizes = excluded.client_sizes, tone = excluded.tone,"
        " priorities = excluded.priorities, time_zone = excluded.time_zone,"
        " about = excluded.about",
        (
            tenant_id,
            data.type,
            data.team_size,
            data.min_budget_usd,
            list(data.client_sizes),
            data.tone,
            list(data.priorities),
            data.time_zone,
            data.about,
        ),
    )

    # Catalogue services: delete the ones removed, add the new ones.
    await conn.execute(
        "delete from public.tenant_services where tenant_id = %s and service_id is not null"
        " and not (service_id = any(%s))",
        (tenant_id, data.services),
    )
    for service_id in data.services:
        await conn.execute(
            "insert into public.tenant_services (tenant_id, service_id) values (%s, %s)"
            " on conflict do nothing",
            (tenant_id, service_id),
        )
    custom = [c.strip() for c in data.custom_services]
    await conn.execute(
        "delete from public.tenant_services where tenant_id = %s and custom_name is not null"
        " and not (lower(custom_name) = any(%s))",
        (tenant_id, [c.lower() for c in custom]),
    )
    for name in custom:
        await conn.execute(
            "insert into public.tenant_services (tenant_id, custom_name) values (%s, %s)"
            " on conflict do nothing",
            (tenant_id, name),
        )

    await _replace_set(conn, "tenant_markets", "market_id", tenant_id, data.markets)
    await _replace_set(conn, "tenant_signals", "signal_type_id", tenant_id, data.signals)

    await conn.execute(
        "delete from public.tenant_exclusions where tenant_id = %s and not (value = any(%s))",
        (tenant_id, data.exclusions),
    )
    existing = await (
        await conn.execute(
            "select value from public.tenant_exclusions where tenant_id = %s", (tenant_id,)
        )
    ).fetchall()
    have = {r["value"] for r in existing}
    for value in dict.fromkeys(data.exclusions):
        if value not in have:
            await conn.execute(
                "insert into public.tenant_exclusions (tenant_id, value) values (%s, %s)",
                (tenant_id, value),
            )

    row = await (
        await conn.execute(
            "select version from public.tenant_profiles where tenant_id = %s", (tenant_id,)
        )
    ).fetchone()
    if row is None:  # RLS hid the row: the caller may not edit this company's profile
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners and admins edit the profile")
    return int(row["version"])


async def _check_catalogue(conn: Conn, table: str, ids: list[UUID]) -> None:
    if not ids:
        return
    row = await (
        await conn.execute(
            f"select count(*) as n from public.{table} where id = any(%s)",  # noqa: S608 - fixed names
            (ids,),
        )
    ).fetchone()
    if row is None or row["n"] != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown {table} id")


async def _replace_set(
    conn: Conn, table: str, column: str, tenant_id: UUID, ids: list[UUID]
) -> None:
    await conn.execute(
        f"delete from public.{table} where tenant_id = %s and not ({column} = any(%s))",  # noqa: S608
        (tenant_id, ids),
    )
    for item in dict.fromkeys(ids):
        await conn.execute(
            f"insert into public.{table} (tenant_id, {column}) values (%s, %s)"  # noqa: S608
            " on conflict do nothing",
            (tenant_id, item),
        )


async def load_profile(conn: Conn, tenant_id: UUID) -> dict[str, Any] | None:
    profile = await (
        await conn.execute(
            "select type, team_size, min_budget_usd, client_sizes, tone, priorities, time_zone,"
            " about, version, compile_status, compiled_version, updated_at"
            " from public.tenant_profiles where tenant_id = %s",
            (tenant_id,),
        )
    ).fetchone()
    if profile is None:
        return None
    services = await (
        await conn.execute(
            "select ts.id, ts.service_id, coalesce(s.name, ts.custom_name) as name,"
            " ts.custom_name is not null as custom"
            " from public.tenant_services ts left join public.services s on s.id = ts.service_id"
            " where ts.tenant_id = %s order by s.sort_order nulls last, name",
            (tenant_id,),
        )
    ).fetchall()
    markets = await (
        await conn.execute(
            "select m.id, m.code, m.name from public.tenant_markets tm"
            " join public.markets m on m.id = tm.market_id where tm.tenant_id = %s"
            " order by m.sort_order",
            (tenant_id,),
        )
    ).fetchall()
    signals = await (
        await conn.execute(
            "select st.id, st.key, st.label, st.temperature from public.tenant_signals ts"
            " join public.signal_types st on st.id = ts.signal_type_id where ts.tenant_id = %s"
            " order by st.sort_order",
            (tenant_id,),
        )
    ).fetchall()
    exclusions = await (
        await conn.execute(
            "select value from public.tenant_exclusions where tenant_id = %s order by value",
            (tenant_id,),
        )
    ).fetchall()
    compiled = await (
        await conn.execute(
            "select profile_version, status, search_terms, finished_at"
            " from public.profile_compilations where tenant_id = %s"
            " order by profile_version desc limit 1",
            (tenant_id,),
        )
    ).fetchone()
    return {
        **profile,
        "services": services,
        "markets": markets,
        "signals": signals,
        "exclusions": [e["value"] for e in exclusions],
        "compiled": compiled,
    }
