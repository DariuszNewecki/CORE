"""Tests for CommitAuthorshipAuditWorker helpers (ADR-129 D4).

The diff helper previously lived as a module-level private function in
commit_authorship_audit_worker.py. It is now centralised in
GitService.diff_file_names (shared sanctuary for async git operations).
Tests moved here accordingly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from shared.infrastructure.git_service import GitService


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> None:
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@adr129.local"], tmp_path)
    _run(["git", "config", "user.name", "ADR129 Worker Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _run(["git", "add", "seed.txt"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)


async def test_diff_file_names_returns_changed_paths(tmp_path: Path) -> None:
    """Files changed between two SHAs are returned correctly."""
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    (tmp_path / "produced.py").write_text("x = 1\n")
    _run(["git", "add", "produced.py"], tmp_path)
    _run(["git", "commit", "-m", "produced"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await GitService(tmp_path).diff_file_names(pre_sha, post_sha)
    assert result is not None
    assert "produced.py" in result


async def test_diff_file_names_detects_extra_files(tmp_path: Path) -> None:
    """When the commit contains files beyond the declared set, they appear."""
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    (tmp_path / "declared.py").write_text("a\n")
    (tmp_path / "contamination.py").write_text("b\n")
    _run(["git", "add", "declared.py", "contamination.py"], tmp_path)
    _run(["git", "commit", "-m", "two files"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await GitService(tmp_path).diff_file_names(pre_sha, post_sha)
    assert result is not None
    extra = set(result) - {"declared.py"}
    assert "contamination.py" in extra


async def test_diff_file_names_returns_none_on_bad_sha(tmp_path: Path) -> None:
    """Invalid SHAs cause diff_file_names to return None rather than raising."""
    _init_repo(tmp_path)
    result = await GitService(tmp_path).diff_file_names("0" * 40, "1" * 40)
    assert result is None


async def test_diff_file_names_empty_for_no_changes(tmp_path: Path) -> None:
    """Identical SHAs yield an empty list (no diff)."""
    _init_repo(tmp_path)
    sha = _run(["git", "rev-parse", "HEAD"], tmp_path)
    result = await GitService(tmp_path).diff_file_names(sha, sha)
    assert result == []
