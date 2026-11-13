from __future__ import annotations

from fastapi import APIRouter, status

from api.auth import CurrentUser
from api.models import CreateCompany, CreatedCompany
from core.db import user_db

router = APIRouter(tags=["companies"])


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_company(body: CreateCompany, user: CurrentUser) -> CreatedCompany:
    # private.create_tenant creates the company and the owner membership in one
    # transaction, caps companies per user and writes the audit entry.
    async with user_db(user.claims) as conn:
        row = await (
            await conn.execute("select private.create_tenant(%s, %s) as id", (body.name, body.type))
        ).fetchone()
    assert row is not None
    return CreatedCompany(id=row["id"])
