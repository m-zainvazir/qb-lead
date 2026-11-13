import importlib.util
from pathlib import Path
from types import ModuleType

HOOKS = Path(__file__).parent


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard_commands = _load("guard_commands")
guard_files = _load("guard_files")


def test_blocks_remote_or_unqualified_reset() -> None:
    assert guard_commands.reason_to_block("npx supabase db reset")
    assert guard_commands.reason_to_block("supabase db reset --linked")
    assert guard_commands.reason_to_block("supabase db reset --local --db-url postgres://x")


def test_allows_local_reset_and_normal_commands() -> None:
    assert guard_commands.reason_to_block("npx supabase db reset --local") is None
    assert guard_commands.reason_to_block("uv run pytest -q") is None
    assert guard_commands.reason_to_block("cat .env.example") is None


def test_blocks_destructive_sql_and_env_writes() -> None:
    assert guard_commands.reason_to_block('psql -c "DROP TABLE leads"')
    assert guard_commands.reason_to_block('psql -c "truncate audit_log"')
    assert guard_commands.reason_to_block("echo KEY=1 >> .env")
    assert guard_commands.reason_to_block("sed -i 's/a/b/' apps/web/.env.local")
    assert guard_commands.reason_to_block("supabase db push")


def test_blocks_env_and_key_files() -> None:
    assert guard_files.reason_to_block(".env")
    assert guard_files.reason_to_block("apps/web/.env.local")
    assert guard_files.reason_to_block("certs/server.key")
    assert guard_files.reason_to_block(".env.example") is None
    assert guard_files.reason_to_block("apps/api/api/main.py") is None


def test_blocks_committed_migration() -> None:
    root = Path(__file__).resolve().parents[2]
    committed = sorted((root / "supabase" / "migrations").glob("*_init.sql"))[0]
    assert guard_files.reason_to_block(str(committed))
