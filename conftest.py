"""Root pytest config: a fake, complete environment for unit tests.

Unit tests never talk to real services. Tests that need the database (staging) are
marked `db` and read the real values from `.env` / `.env.test.local` instead.
"""

from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    # psycopg's async mode needs a selector event loop on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined,unused-ignore]

_FAKE_ENV = {
    "APP_ENV": "test",
    "SUPABASE_URL": "http://127.0.0.1:54321",
    "SUPABASE_ANON_KEY": "anon-key",
    "DATABASE_URL_API": "postgresql://app_api:x@127.0.0.1:54322/postgres",
    "DATABASE_URL_SYSTEM": "postgresql://app_system:x@127.0.0.1:54322/postgres",
    "REDIS_URL": "redis://:x@127.0.0.1:6379/0",
    "GIT_COMMIT": "testsha",
}

if os.environ.get("LEADGEN_USE_REAL_ENV") != "1":
    for key, value in _FAKE_ENV.items():
        os.environ.setdefault(key, value)
else:
    # Real values (database tests): refuse anything that is not local or a staging
    # project in .claude/staging-targets.txt, and production (core.targets).
    from dotenv import dotenv_values

    from core.targets import UnsafeTarget, check

    _real = {**dotenv_values(".env"), **os.environ}
    try:
        check(
            *(str(_real[k]) for k in ("SUPABASE_URL", "DATABASE_URL_API") if _real.get(k)),
            *([str(_real["DATABASE_URL_ADMIN"])] if _real.get("DATABASE_URL_ADMIN") else []),
            app_env=str(_real.get("APP_ENV") or ""),
        )
    except UnsafeTarget as _exc:
        raise SystemExit(f"Refusing to run database tests: {_exc}") from None
