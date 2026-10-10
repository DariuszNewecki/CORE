# tests/shared/infrastructure/test_git_service_adr_refs.py
"""adr_refs_in_history: ADRs cited by commits that touched a file (real git)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.infrastructure.git_service import GitService


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


# ID: 55fd2dd1-3147-4c4e-9adc-4a7887a64375
def test_refs_are_counted_most_cited_first_and_normalised(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.invalid")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    target = tmp_path / "a.py"
    for i, msg in enumerate(
        [
            "feat: ADR-12 start",
            "fix: per ADR-168 D3",
            "docs: ADR-168 again\n\nbody ADR-012",
        ]
    ):
        target.write_text(f"x = {i}\n")
        _git(tmp_path, "add", "a.py")
        _git(tmp_path, "commit", "-q", "-m", msg)
    (tmp_path / "other.py").write_text("y = 1\n")
    _git(tmp_path, "add", "other.py")
    _git(tmp_path, "commit", "-q", "-m", "feat: ADR-999 elsewhere")

    refs = GitService(tmp_path).adr_refs_in_history("a.py")

    assert refs == ["ADR-012", "ADR-168"]


# ID: 49b05088-b521-4ee5-a921-15cd73d56dce
def test_unreadable_history_is_none_not_empty(tmp_path: Path) -> None:
    assert GitService(tmp_path).adr_refs_in_history("a.py") is None
