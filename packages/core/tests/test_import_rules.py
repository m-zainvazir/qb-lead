"""Only the worker and the admin module may use system_db() (CLAUDE.md).

Ruff's TID251 rule catches this at lint time; this test also catches `# noqa`
suppressions and indirect imports such as `from core import db; db.system_db()`.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCANNED = [ROOT / "apps" / "api" / "api", ROOT / "packages" / "core" / "core"]
ALLOWED = [
    ROOT / "apps" / "worker",
    ROOT / "apps" / "api" / "api" / "admin",
    ROOT / "packages" / "core" / "core" / "db.py",
]


def _allowed(path: Path) -> bool:
    return any(path == a or a in path.parents for a in ALLOWED)


def _uses_system_db(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "core.db"
            and any(alias.name in ("system_db", "*") for alias in node.names)
        ):
            return True
        if isinstance(node, ast.Attribute) and node.attr == "system_db":
            return True
        if isinstance(node, ast.Name) and node.id == "system_db":
            return True
        if isinstance(node, ast.Constant) and node.value == "system_db":
            return True  # getattr(db, "system_db")
    return False


def test_system_db_only_in_worker_and_admin() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for base in SCANNED
        for path in base.rglob("*.py")
        if not _allowed(path) and _uses_system_db(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert offenders == [], f"system_db() used outside worker/admin: {offenders}"


def test_service_role_pool_created_in_one_place() -> None:
    hits = [
        path.relative_to(ROOT).as_posix()
        for base in (ROOT / "apps", ROOT / "packages")
        for path in base.rglob("*.py")
        if ".venv" not in path.parts
        and "node_modules" not in path.parts
        and "tests" not in path.parts
        and "database_url_system" in path.read_text(encoding="utf-8")
    ]
    # settings.py only declares the variable; db.py is the one place that connects with it.
    assert sorted(hits) == ["packages/core/core/db.py", "packages/core/core/settings.py"], hits
