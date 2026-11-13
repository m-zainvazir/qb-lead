"""Root pytest config: a fake, complete environment for unit tests.

Unit tests never talk to real services. Tests that need the local database are
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
