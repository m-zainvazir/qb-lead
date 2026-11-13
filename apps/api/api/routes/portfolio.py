"""Portfolio files: upload (checked by content), list, short-lived download link, delete."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel

from api import storage
from api.auth import CurrentTenant
from api.filetypes import name_matches, sniff
from core.db import user_db
from core.features import can
from core.jobs import enqueue

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

MAX_BYTES = 10 * 1024 * 1024


class PortfolioItem(BaseModel):
    id: UUID
    title: str
    mime_type: str
    size_bytes: int
    status: str
    summary: str | None
    error: str | None
    created_at: datetime


def _token(request: Request) -> str:
    return request.headers["authorization"].split(" ", 1)[1].strip()


@router.get("")
async def list_items(ctx: CurrentTenant) -> list[PortfolioItem]:
    async with user_db(ctx.claims) as conn:
        rows = await (
            await conn.execute(
                "select id, title, mime_type, size_bytes, status, summary, error, created_at"
                " from public.portfolio_items"
                " where tenant_id = %s order by created_at desc limit 100",
                (ctx.tenant_id,),
            )
        ).fetchall()
    return [PortfolioItem(**r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_item(
    request: Request,
    ctx: CurrentTenant,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=200)] = None,
) -> PortfolioItem:
    ctx.require_role("owner", "admin")
    if not await can(ctx.tenant_id, "portfolio.upload"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not available on your plan")

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Files are limited to 10 MB")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file is empty")
    filetype = sniff(data)
    filename = file.filename or ""
    if filetype is None or not name_matches(filename, filetype):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload a PDF, Word (.docx) or text file"
        )

    clean_title = (title or filename.rsplit(".", 1)[0] or "Portfolio item").strip()[:200]
    clean_title = "".join(ch for ch in clean_title if ch.isprintable()) or "Portfolio item"
    path = f"{ctx.tenant_id}/{secrets.token_hex(16)}{filetype.ext}"

    await storage.upload(_token(request), path, data, filetype.mime)
    try:
        async with user_db(ctx.claims) as conn:
            row = await (
                await conn.execute(
                    "insert into public.portfolio_items"
                    " (tenant_id, title, file_path, mime_type, size_bytes)"
                    " values (%s, %s, %s, %s, %s)"
                    " returning id, title, mime_type, size_bytes, status, summary, error,"
                    " created_at",
                    (ctx.tenant_id, clean_title, path, filetype.mime, len(data)),
                )
            ).fetchone()
    except Exception:
        await storage.delete(_token(request), path)
        raise
    assert row is not None
    await enqueue("worker.tasks.process_portfolio_item", str(row["id"]))
    return PortfolioItem(**row)


@router.get("/{item_id}/download")
async def download_link(item_id: UUID, request: Request, ctx: CurrentTenant) -> dict[str, Any]:
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute(
                "select file_path from public.portfolio_items where id = %s and tenant_id = %s",
                (item_id, ctx.tenant_id),
            )
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    url = await storage.signed_url(_token(request), row["file_path"])
    return {"url": url, "expires_in": storage.SIGNED_URL_SECONDS}


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: UUID, request: Request, ctx: CurrentTenant) -> Response:
    ctx.require_role("owner", "admin")
    async with user_db(ctx.claims) as conn:
        row = await (
            await conn.execute(
                "delete from public.portfolio_items where id = %s and tenant_id = %s"
                " returning file_path",
                (item_id, ctx.tenant_id),
            )
        ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    await storage.delete(_token(request), row["file_path"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
