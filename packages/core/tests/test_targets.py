"""core.targets: tests, seeding and pushes only touch local or listed staging projects."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.targets import UnsafeTarget, check, project_ref

STAGING = "stagingref123"
PROD = "prodref456"
POOLER = "aws-1-us-east-1.pooler.supabase.com"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "staging-targets.txt").write_text(f"# staging\n{STAGING}\n")
    (tmp_path / ".claude" / "protected-targets.txt").write_text(f"# prod\n{PROD}\n")
    return tmp_path


@pytest.mark.parametrize(
    ("url", "ref"),
    [
        (f"https://{STAGING}.supabase.co", STAGING),
        (f"postgresql://postgres:x@db.{STAGING}.supabase.co:5432/postgres", STAGING),
        (f"postgresql://app_api.{STAGING}:x@{POOLER}:5432/postgres", STAGING),
        ("postgresql://app_api:x@127.0.0.1:54322/postgres", None),
        ("https://example.com", None),
    ],
)
def test_project_ref(url: str, ref: str | None) -> None:
    assert project_ref(url) == ref


def test_staging_and_local_are_allowed(root: Path) -> None:
    assert check(f"https://{STAGING}.supabase.co", root=root) == STAGING
    assert check(f"postgresql://app_api.{STAGING}:x@{POOLER}/postgres", root=root) == STAGING
    assert check("http://127.0.0.1:54321", "postgresql://a:x@localhost/postgres", root=root) == (
        "local"
    )


@pytest.mark.parametrize(
    "url",
    [
        f"https://{PROD}.supabase.co",  # protected
        "https://otherref999.supabase.co",  # not listed as staging
        "postgresql://postgres:x@db.example.com:5432/postgres",  # unknown host
    ],
)
def test_everything_else_is_refused(root: Path, url: str) -> None:
    with pytest.raises(UnsafeTarget):
        check(url, root=root)


def test_production_env_is_refused_even_for_staging(root: Path) -> None:
    with pytest.raises(UnsafeTarget):
        check(f"https://{STAGING}.supabase.co", app_env="production", root=root)


def test_mixed_targets_are_refused(root: Path) -> None:
    with pytest.raises(UnsafeTarget):
        check(f"https://{STAGING}.supabase.co", "postgresql://a:x@127.0.0.1/postgres", root=root)
