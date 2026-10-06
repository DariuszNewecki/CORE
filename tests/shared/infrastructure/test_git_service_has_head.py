"""GitService.has_head (#958): whether HEAD resolves to a commit, without
logging a git failure for the freshly initialised case."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.git_service import GitService


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_fresh_repository_has_no_head_and_logs_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _git(tmp_path, "init", "-q")
    with caplog.at_level("DEBUG"):
        assert GitService(tmp_path).has_head() is False
    assert not [r for r in caplog.records if r.levelno >= 30]


def test_repository_with_a_commit_has_head(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("x\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "first")
    assert GitService(tmp_path).has_head() is True
