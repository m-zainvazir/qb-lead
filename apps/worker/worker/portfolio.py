"""Portfolio processing: download -> extract (sandboxed child) -> summary -> embedding.

Idempotent: an item that is already processed with the current model is skipped unless
forced (re-embed). Failures are stored on the item so the screen can say what happened.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from uuid import UUID

import httpx

from core.db import system_db_sync
from core.embeddings import get_embedder, to_pgvector
from core.metering import metered_call
from core.settings import get_settings

log = logging.getLogger(__name__)

EXTRACT_TIMEOUT_S = 30
EXTRACT_MEMORY_BYTES = 512 * 1024 * 1024
MAX_DOWNLOAD = 10 * 1024 * 1024


def _limit_child() -> None:  # pragma: no cover - runs in the child, Linux only
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (EXTRACT_MEMORY_BYTES, EXTRACT_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (EXTRACT_TIMEOUT_S, EXTRACT_TIMEOUT_S))


def extract_text(data: bytes, mime: str) -> str:
    """Run extraction in a separate process with a timeout (and memory cap on Linux)."""
    proc = subprocess.run(  # noqa: S603 - fixed interpreter and module, no shell
        [sys.executable, "-m", "worker.extract_child", mime],
        input=data,
        capture_output=True,
        timeout=EXTRACT_TIMEOUT_S,
        preexec_fn=_limit_child if sys.platform.startswith("linux") else None,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError("could not read the file")
    return proc.stdout.decode("utf-8", errors="replace")


def summarise(text: str, limit: int = 500) -> str:
    """A plain extract: the first sentences, up to `limit` characters."""
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > limit // 3 else cut.rsplit(" ", 1)[0] + "â€¦").strip()


def _download(path: str) -> bytes:
    s = get_settings()
    if s.supabase_service_role_key is None:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required by the worker")
    key = s.supabase_service_role_key.get_secret_value()
    url = f"{s.supabase_url.rstrip('/')}/storage/v1/object/{s.storage_bucket}/{path}"
    with httpx.stream(
        "GET", url, headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=30
    ) as res:
        res.raise_for_status()
        chunks, total = [], 0
        for chunk in res.iter_bytes():
            total += len(chunk)
            if total > MAX_DOWNLOAD:
                raise ValueError("file is larger than allowed")
            chunks.append(chunk)
    return b"".join(chunks)


def process_item(item_id: UUID, *, force: bool = False) -> str:
    embedder = get_embedder()
    with system_db_sync() as conn:
        item = conn.execute(
            "select id, tenant_id, file_path, mime_type, status, embedding_model"
            " from public.portfolio_items where id = %s for update",
            (item_id,),
        ).fetchone()
        if item is None:
            return "gone"
        if item["status"] == "ready" and item["embedding_model"] == embedder.model and not force:
            return "already-processed"
        conn.execute(
            "update public.portfolio_items set status = 'processing', error = null where id = %s",
            (item_id,),
        )
    try:
        text = extract_text(_download(item["file_path"]), item["mime_type"])
        if not text.strip():
            raise ValueError("no text found in the file (scanned images are not read yet)")
        summary = summarise(text)
        source = (summary + "\n" + text[:4000])[:4500]
        vector = metered_call(
            lambda: embedder.embed([source])[0],
            provider=embedder.model,
            operation="embed.portfolio_item",
            tenant_id=item["tenant_id"],
            units=len(source) / 1000,
            unit="1k_chars",
            unit_cost_usd=get_settings().embedding_cost_per_1k_chars,
            metadata={"portfolio_item_id": str(item_id)},
        )
    except (ValueError, subprocess.TimeoutExpired, httpx.HTTPError) as exc:
        message = (
            "reading the file took too long"
            if isinstance(exc, subprocess.TimeoutExpired)
            else str(exc)
        )
        with system_db_sync() as conn:
            conn.execute(
                "update public.portfolio_items set status = 'failed', error = %s where id = %s",
                (message[:2000], item_id),
            )
        log.warning("portfolio_item_failed", extra={"item_id": str(item_id), "error": message})
        return "failed"
    with system_db_sync() as conn:
        conn.execute(
            "update public.portfolio_items set status = 'ready', summary = %s,"
            " extracted_chars = %s, embedding = %s::extensions.vector, embedding_model = %s,"
            " error = null where id = %s",
            (summary, len(text), to_pgvector(vector), embedder.model, item_id),
        )
    return "processed"


def re_embed_all() -> int:
    """Recompute portfolio vectors with the current model. Returns how many were updated."""
    with system_db_sync() as conn:
        ids = [
            r["id"]
            for r in conn.execute(
                "select id from public.portfolio_items where status = 'ready' order by created_at"
            ).fetchall()
        ]
    return sum(1 for item_id in ids if process_item(item_id, force=True) == "processed")
