"""GitService.committed_bytes: a file's exact bytes at a revision, None when
the revision has no such file, RuntimeError when git cannot answer."""

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


def test_returns_exact_committed_bytes_not_the_working_copy(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    raw = b"line one\r\n\xff\x00trailing  \n\n"
    (tmp_path / "law.yaml").write_bytes(raw)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "first")
    (tmp_path / "law.yaml").write_bytes(b"changed\n")
    assert GitService(tmp_path).committed_bytes("law.yaml") == raw


def test_file_absent_at_head_is_none(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("a\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "first")
    assert GitService(tmp_path).committed_bytes("missing.txt") is None


def test_no_repository_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        GitService(tmp_path).committed_bytes("a.txt")
