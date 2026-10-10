# tests/shared/infrastructure/test_git_service_sandbox_ownership.py
"""A live sandbox is never swept; a vanished one never falls through (real git).

Proposal da93593b (2026-10-10): every worker's boot sweep removed a sandbox
another process was using; its git commands then discovered the enclosing main
repository, `git apply` ignored the patch's paths and exited 0, and the
proposal was marked completed with nothing applied.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.git_service import (
    GitService,
    _sandbox_owner_gone,
    _worktree_entries,
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> GitService:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t.invalid")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return GitService(tmp_path)


def _dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


# ID: a4e6370c-f01b-44b7-b949-64d508674553
def test_a_sandbox_is_created_locked_by_its_owner(repo: GitService) -> None:
    sandbox = repo.create_worktree(repo.get_current_commit())
    try:
        entries = dict(
            _worktree_entries(_git(repo.repo_path, "worktree", "list", "--porcelain"))
        )
        assert entries[str(sandbox.repo_path)] == f"core-sandbox pid={os.getpid()}"
    finally:
        sandbox.cleanup()
    assert not sandbox.repo_path.exists()


# ID: 1ff5a615-d704-4dd9-a56c-f9a30c19e69e
def test_the_sweep_leaves_a_live_sandbox_alone(repo: GitService) -> None:
    sandbox = repo.create_worktree(repo.get_current_commit())
    try:
        assert repo.sweep_orphan_worktrees() == 0
        assert (sandbox.repo_path / ".git").exists()
    finally:
        sandbox.cleanup()


# ID: b179c4f8-7e7f-4553-b9d2-0e2d4e668104
def test_the_sweep_removes_a_sandbox_whose_owner_is_gone(repo: GitService) -> None:
    sandbox = repo.create_worktree(repo.get_current_commit())
    _git(repo.repo_path, "worktree", "unlock", str(sandbox.repo_path))
    _git(
        repo.repo_path,
        "worktree",
        "lock",
        "--reason",
        f"core-sandbox pid={_dead_pid()}",
        str(sandbox.repo_path),
    )

    assert repo.sweep_orphan_worktrees() == 1
    assert not sandbox.repo_path.exists()


# ID: bdfc7d66-7b66-40c0-87c4-c059c75ac77c
def test_a_vanished_sandbox_refuses_instead_of_using_the_main_repo(
    repo: GitService,
) -> None:
    sandbox = repo.create_worktree(repo.get_current_commit())
    try:
        (sandbox.repo_path / ".git").unlink()
        with pytest.raises(RuntimeError, match="vanished"):
            sandbox.status_porcelain()
    finally:
        shutil.rmtree(sandbox.repo_path, ignore_errors=True)
        _git(repo.repo_path, "worktree", "prune")


# ID: 4670d09d-981d-45dd-bd57-2e430d4365e8
def test_owner_rules() -> None:
    assert _sandbox_owner_gone(None) is True
    assert _sandbox_owner_gone("initializing") is False
    assert _sandbox_owner_gone(f"core-sandbox pid={os.getpid()}") is False
    assert _sandbox_owner_gone(f"core-sandbox pid={_dead_pid()}") is True
    assert _sandbox_owner_gone("core-sandbox pid=notanumber") is False
