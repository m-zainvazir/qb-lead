"""Discovers tables at collection time, so a new table is tested without anyone
remembering to add it."""

from __future__ import annotations

import psycopg

from core.settings import get_settings


def _query(sql: str) -> list[str]:
    url = get_settings().database_url_admin
    assert url is not None, "DATABASE_URL_ADMIN must be set (run `make env`)"
    with psycopg.connect(url.get_secret_value()) as conn:
        return [r[0] for r in conn.execute(sql).fetchall()]


PUBLIC_TABLES = _query(
    "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
    " where n.nspname = 'public' and c.relkind in ('r', 'p') order by 1"
)

TENANT_TABLES = sorted(
    set(
        _query(
            "select c.table_name from information_schema.columns c"
            " join information_schema.tables t"
            "   on t.table_schema = c.table_schema and t.table_name = c.table_name"
            " where c.table_schema = 'public' and c.column_name = 'tenant_id'"
            "   and t.table_type = 'BASE TABLE'"
        )
    )
    | {"tenants"}
)
