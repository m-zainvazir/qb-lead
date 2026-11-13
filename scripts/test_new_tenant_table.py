from pathlib import Path

import pytest
from check_migrations import check
from new_tenant_table import render


def test_rendered_template_passes_rls_check(tmp_path: Path) -> None:
    p = tmp_path / "20260101000000_create_leads.sql"
    p.write_text(render("leads"), encoding="utf-8")
    assert check(p) == []
    assert "__TABLE__" not in p.read_text(encoding="utf-8")


def test_template_has_four_policies_on_is_member() -> None:
    sql = render("leads")
    for cmd in ("select", "insert", "update", "delete"):
        assert f"create policy leads_{cmd} on public.leads for {cmd}" in sql
    assert sql.count("private.is_member(tenant_id)") == 5  # update has using + with check


@pytest.mark.parametrize("bad", ["Leads", "x", "leads; drop", "1abc"])
def test_rejects_bad_names(bad: str) -> None:
    with pytest.raises(ValueError):
        render(bad)
