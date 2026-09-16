# tests/body/self_healing/test_id_assignment_handler__orphan_shadow.py

"""The linkage.assign_ids finding handler must not regenerate an identity an
orphaned anchor still carries (linkage.no_orphan_ids)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from body.self_healing.handlers.id_assignment_handler import (
    assign_missing_ids_handler,
)


_ORPHAN_LINE = "# ID: a1fb17c6-a4a7-4503-9103-491b28305c2d"
_SOURCE = (
    f"{_ORPHAN_LINE}\n"
    "\n"
    "def shadowed():\n"
    "    return 1\n"
    "\n"
    "\n"
    "def unrelated():\n"
    "    return 2\n"
)


async def test_dry_run_plans_only_the_unrelated_symbol(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "probe.py").write_text(_SOURCE, encoding="utf-8")
    finding = SimpleNamespace(file_path="src/probe.py", message="m")

    result = await assign_missing_ids_handler(
        finding,  # type: ignore[arg-type]
        file_handler=None,  # type: ignore[arg-type]
        repo_root=tmp_path,
        write=False,
    )

    assert result.ok
    assert result.changes_made["would_insert"] == 1
    assert result.changes_made["symbols"] == ["unrelated"]
