from pathlib import Path

from check_migrations import check


def _write(tmp_path: Path, sql: str) -> Path:
    p = tmp_path / "20260101000000_x.sql"
    p.write_text(sql, encoding="utf-8")
    return p


def test_table_without_rls_fails(tmp_path: Path) -> None:
    errors = check(_write(tmp_path, "create table public.leads (id int);"))
    assert len(errors) == 2


def test_table_with_rls_passes(tmp_path: Path) -> None:
    sql = """
    create table if not exists leads (id int);
    alter table public.leads enable row level security;
    alter table leads force row level security;
    """
    assert check(_write(tmp_path, sql)) == []


def test_commented_out_rls_does_not_count(tmp_path: Path) -> None:
    sql = "create table leads (id int);\n-- alter table leads enable row level security;\n"
    assert check(_write(tmp_path, sql))
