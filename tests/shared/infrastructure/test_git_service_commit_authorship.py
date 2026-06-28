"""Tests for ADR-129 D1 — staging-area contamination check in commit_paths.

GitService.commit_paths() uses two layers of protection:
  Layer 1 (check): raises early if staging area contains paths outside the
    declared production set.
  Layer 2 (pathspec): ``git commit -- paths`` restricts the commit object to
    the production paths regardless of what else is in the index — belt-and-
    suspenders against the nanosecond race window between Layer 1 and git-add.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.git_service import GitService, StagingContaminationError


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> GitService:
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@adr129.local"], tmp_path)
    _run(["git", "config", "user.name", "ADR129 Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _run(["git", "add", "seed.txt"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return GitService(tmp_path)


def test_commit_paths_accepts_clean_staging_area(tmp_path: Path) -> None:
    """Happy path: no extra staged files — commit_paths proceeds normally."""
    svc = _init_repo(tmp_path)
    (tmp_path / "produced.py").write_text("x = 1\n")
    svc.commit_paths(["produced.py"], "fix(test): produced file")
    sha = _run(["git", "rev-parse", "HEAD"], tmp_path)
    diff = _run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], tmp_path)
    assert "produced.py" in diff
    assert sha  # commit happened


def test_commit_paths_raises_on_extra_staged_path(tmp_path: Path) -> None:
    """ADR-129 D1: extra staged file outside production set → RuntimeError."""
    svc = _init_repo(tmp_path)
    # Simulate a concurrent session staging a file.
    (tmp_path / "governor_wip.py").write_text("# work in progress\n")
    _run(["git", "add", "governor_wip.py"], tmp_path)

    # Autonomous action wants to commit only its own production.
    (tmp_path / "produced.py").write_text("x = 1\n")

    with pytest.raises(StagingContaminationError, match="ADR-129 D1"):
        svc.commit_paths(["produced.py"], "fix(test): autonomous commit")

    # The staging area must not have been disturbed — WIP file still staged.
    staged = _run(["git", "diff", "--cached", "--name-only"], tmp_path)
    assert "governor_wip.py" in staged


def test_commit_paths_raises_staging_contamination_error_not_runtime_error(
    tmp_path: Path,
) -> None:
    """D1 fires as StagingContaminationError (subclass of RuntimeError) so
    callers can distinguish it from ordinary git failures (ADR-129 D7)."""
    svc = _init_repo(tmp_path)
    (tmp_path / "wip.py").write_text("# wip\n")
    _run(["git", "add", "wip.py"], tmp_path)
    (tmp_path / "produced.py").write_text("x = 1\n")

    with pytest.raises(StagingContaminationError) as exc_info:
        svc.commit_paths(["produced.py"], "fix(test): should be refused")

    # Subclass of RuntimeError — existing broad except RuntimeError handlers
    # still catch it; callers that want to distinguish can narrow to
    # StagingContaminationError first.
    assert isinstance(exc_info.value, RuntimeError)


def test_commit_paths_raises_lists_extra_paths_in_message(tmp_path: Path) -> None:
    """The StagingContaminationError message names the contaminating paths (up to 3)."""
    svc = _init_repo(tmp_path)
    for i in range(4):
        (tmp_path / f"wip_{i}.py").write_text(f"# wip {i}\n")
        _run(["git", "add", f"wip_{i}.py"], tmp_path)

    (tmp_path / "produced.py").write_text("x = 1\n")

    with pytest.raises(StagingContaminationError) as exc_info:
        svc.commit_paths(["produced.py"], "fix(test): autonomous commit")

    msg = str(exc_info.value)
    assert "ADR-129 D1" in msg
    # Shows up to 3 samples and an ellipsis for the remainder.
    assert "wip_" in msg


def test_commit_paths_commit_object_bounded_to_production(tmp_path: Path) -> None:
    """Layer 2: the commit object contains ONLY the declared production paths.

    Verifies that bystander files modified in the working tree do not land
    in the commit even when they're not staged — and that the production files
    do. This exercises the pathspec-restricted ``git commit -- paths`` command.
    """
    svc = _init_repo(tmp_path)
    (tmp_path / "produced.py").write_text("x = 1\n")
    (tmp_path / "bystander.py").write_text("# not produced\n")
    # bystander.py is untracked/modified but deliberately NOT passed to commit_paths
    svc.commit_paths(["produced.py"], "fix(test): production only")
    diff = _run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], tmp_path)
    assert "produced.py" in diff
    assert "bystander.py" not in diff


def test_get_staged_paths_empty_when_nothing_staged(tmp_path: Path) -> None:
    """_get_staged_paths returns empty set on a clean working tree."""
    svc = _init_repo(tmp_path)
    assert svc._get_staged_paths() == set()


def test_get_staged_paths_returns_staged_files(tmp_path: Path) -> None:
    """_get_staged_paths correctly reflects the index."""
    svc = _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("a\n")
    (tmp_path / "b.py").write_text("b\n")
    _run(["git", "add", "a.py", "b.py"], tmp_path)
    staged = svc._get_staged_paths()
    assert staged == {"a.py", "b.py"}
