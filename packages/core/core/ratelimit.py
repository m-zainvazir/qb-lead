"""Fixed-window rate limits keyed by a string (for example a webhook secret's hash).

Redis is the shared counter; if Redis is unreachable a per-process counter takes over,
so ingestion keeps working (more leniently) instead of failing.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from functools import lru_cache

import redis.asyncio as aioredis

from core.settings import get_settings

log = logging.getLogger(__name__)
_local: dict[str, int] = defaultdict(int)


@lru_cache(maxsize=1)
def _redis() -> aioredis.Redis:
    return aioredis.from_url(
        get_settings().redis_url.get_secret_value(), socket_timeout=1, socket_connect_timeout=1
    )


async def hit(key: str, limit: int, window_s: int = 60) -> bool:
    """Count one request; True while within `limit` per `window_s` seconds."""
    window = int(time.time() // window_s)
    name = f"rl:{key}:{window}"
    try:
        count = int(await _redis().incr(name))
        if count == 1:
            await _redis().expire(name, window_s + 5)
    except Exception:
        log.warning("ratelimit_redis_unavailable")
        for stale in [k for k in _local if not k.endswith(f":{window}")]:
            del _local[stale]
        _local[name] += 1
        count = _local[name]
    return count <= limit


async def seen_before(key: str, ttl_s: int = 900) -> bool:
    """Replay guard: True if this key was already used within `ttl_s` (fails open)."""
    try:
        return not bool(await _redis().set(f"once:{key}", "1", nx=True, ex=ttl_s))
    except Exception:
        log.warning("replay_guard_redis_unavailable")
        return False
