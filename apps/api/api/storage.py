"""Supabase Storage calls made with the signed-in user's token, so storage policies apply."""

from __future__ import annotations

from urllib.parse import quote

import httpx
from fastapi import HTTPException, status

from core.settings import get_settings

SIGNED_URL_SECONDS = 60


def _base() -> str:
    return get_settings().supabase_url.rstrip("/") + "/storage/v1"


def _headers(token: str) -> dict[str, str]:
    return {
        "apikey": get_settings().supabase_anon_key.get_secret_value(),
        "Authorization": f"Bearer {token}",
    }


def _bucket() -> str:
    return get_settings().storage_bucket


async def upload(token: str, path: str, data: bytes, mime: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{_base()}/object/{_bucket()}/{quote(path)}",
            headers={**_headers(token), "Content-Type": mime, "x-upsert": "false"},
            content=data,
        )
    if res.status_code >= 400:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Storage refused the upload")


async def signed_url(token: str, path: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            f"{_base()}/object/sign/{_bucket()}/{quote(path)}",
            headers=_headers(token),
            json={"expiresIn": SIGNED_URL_SECONDS},
        )
    if res.status_code >= 400:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    signed = str(res.json()["signedURL"])
    if signed.startswith("http"):  # keep only path + token, then use the browser-facing host
        signed = "/" + signed.split("/storage/v1/", 1)[1]
    return f"{get_settings().public_supabase_url}/storage/v1{signed}"


async def delete(token: str, path: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        await client.request(
            "DELETE",
            f"{_base()}/object/{_bucket()}",
            headers=_headers(token),
            json={"prefixes": [path]},
        )
