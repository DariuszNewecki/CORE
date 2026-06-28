"""Tests for CommitAuthorshipAuditWorker helpers (ADR-129 D4).

Tests the _get_diff_files helper that forms the core of the authorship check
without wiring the full worker / blackboard stack.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from will.workers.commit_authorship_audit_worker import _get_diff_files


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


async def test_get_diff_files_returns_changed_paths(tmp_path: Path) -> None:
    """Files changed between two SHAs are returned correctly."""
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    (tmp_path / "produced.py").write_text("x = 1\n")
    _run(["git", "add", "produced.py"], tmp_path)
    _run(["git", "commit", "-m", "produced"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await _get_diff_files(str(tmp_path), pre_sha, post_sha)
    assert result is not None
    assert "produced.py" in result


async def test_get_diff_files_detects_extra_files(tmp_path: Path) -> None:
    """When the commit contains files beyond the declared set, they appear."""
    _init_repo(tmp_path)
    pre_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    (tmp_path / "declared.py").write_text("a\n")
    (tmp_path / "contamination.py").write_text("b\n")
    _run(["git", "add", "declared.py", "contamination.py"], tmp_path)
    _run(["git", "commit", "-m", "two files"], tmp_path)
    post_sha = _run(["git", "rev-parse", "HEAD"], tmp_path)

    result = await _get_diff_files(str(tmp_path), pre_sha, post_sha)
    assert result is not None
    declared = {"declared.py"}
    extra = set(result) - declared
    assert "contamination.py" in extra


async def test_get_diff_files_returns_none_on_bad_sha(tmp_path: Path) -> None:
    """Invalid SHAs cause _get_diff_files to return None rather than raising."""
    _init_repo(tmp_path)
    result = await _get_diff_files(str(tmp_path), "0" * 40, "1" * 40)
    assert result is None


async def test_get_diff_files_empty_for_no_changes(tmp_path: Path) -> None:
    """Identical SHAs yield an empty list (no diff)."""
    _init_repo(tmp_path)
    sha = _run(["git", "rev-parse", "HEAD"], tmp_path)
    result = await _get_diff_files(str(tmp_path), sha, sha)
    assert result == []
