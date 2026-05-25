"""Unit tests for the GitService worktree primitive (ADR-071 D2.2 Phase 1).

Verifies the hermetic sandbox lifecycle in isolation. No executor wiring,
no copy-back — those land with Phase 2.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared.infrastructure.git_service import (
    SANDBOX_PARENT,
    SANDBOX_PREFIX,
    GitService,
    ScopedGitService,
)


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> GitService:
    """Real git repo with one commit; fresh per test for isolation."""
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "test@worktree.local"], tmp_path)
    _run(["git", "config", "user.name", "Worktree Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / "file.txt").write_text("hello\n")
    _run(["git", "add", "file.txt"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return GitService(tmp_path)


def test_create_worktree_returns_scoped_service_at_sha(repo: GitService) -> None:
    sha = repo.get_current_commit()
    scoped = repo.create_worktree(sha)
    try:
        assert isinstance(scoped, ScopedGitService)
        assert scoped.repo_path.exists()
        assert scoped.repo_path.parent == SANDBOX_PARENT
        assert scoped.repo_path.name.startswith(SANDBOX_PREFIX)
        assert scoped.get_current_commit() == sha
        assert (scoped.repo_path / "file.txt").read_text() == "hello\n"
    finally:
        scoped.cleanup()


def test_each_worktree_gets_unique_path(repo: GitService) -> None:
    sha = repo.get_current_commit()
    a = repo.create_worktree(sha)
    b = repo.create_worktree(sha)
    try:
        assert a.repo_path != b.repo_path
        assert a.repo_path.name.startswith(SANDBOX_PREFIX)
        assert b.repo_path.name.startswith(SANDBOX_PREFIX)
    finally:
        a.cleanup()
        b.cleanup()


def test_write_inside_worktree_does_not_leak_to_main_tree(
    repo: GitService,
) -> None:
    sha = repo.get_current_commit()
    scoped = repo.create_worktree(sha)
    try:
        (scoped.repo_path / "file.txt").write_text("changed in sandbox\n")
        assert (repo.repo_path / "file.txt").read_text() == "hello\n"
    finally:
        scoped.cleanup()


def test_cleanup_removes_worktree_directory(repo: GitService) -> None:
    sha = repo.get_current_commit()
    scoped = repo.create_worktree(sha)
    path = scoped.repo_path
    assert path.exists()
    scoped.cleanup()
    assert not path.exists()


def test_cleanup_is_idempotent(repo: GitService) -> None:
    sha = repo.get_current_commit()
    scoped = repo.create_worktree(sha)
    scoped.cleanup()
    scoped.cleanup()  # must not raise


def test_context_manager_cleans_up_on_exit(repo: GitService) -> None:
    sha = repo.get_current_commit()
    with repo.create_worktree(sha) as scoped:
        path = scoped.repo_path
        assert path.exists()
    assert not path.exists()


def test_context_manager_cleans_up_on_exception(repo: GitService) -> None:
    sha = repo.get_current_commit()
    captured: Path | None = None
    with pytest.raises(RuntimeError, match="boom"):
        with repo.create_worktree(sha) as scoped:
            captured = scoped.repo_path
            raise RuntimeError("boom")
    assert captured is not None
    assert not captured.exists()


def test_can_recreate_worktree_at_same_sha_after_cleanup(
    repo: GitService,
) -> None:
    sha = repo.get_current_commit()
    a = repo.create_worktree(sha)
    a.cleanup()
    b = repo.create_worktree(sha)
    try:
        assert b.get_current_commit() == sha
    finally:
        b.cleanup()


def test_sweep_removes_orphan_sandbox_worktree(repo: GitService) -> None:
    sha = repo.get_current_commit()
    abandoned = repo.create_worktree(sha)
    abandoned_path = abandoned.repo_path
    # Simulate crash: skip cleanup entirely.
    assert abandoned_path.exists()

    removed = repo.sweep_orphan_worktrees()

    assert removed >= 1
    assert not abandoned_path.exists()


def test_sweep_skips_non_sandbox_worktrees(
    repo: GitService, tmp_path: Path
) -> None:
    sha = repo.get_current_commit()
    other = tmp_path / "human-checkout"
    _run(
        ["git", "worktree", "add", "--detach", str(other), sha],
        repo.repo_path,
    )
    sandbox = repo.create_worktree(sha)
    sandbox_path = sandbox.repo_path

    try:
        removed = repo.sweep_orphan_worktrees()
        assert removed >= 1
        assert not sandbox_path.exists()
        assert other.exists(), "non-sandbox worktree must not be swept"
    finally:
        if other.exists():
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(other)],
                cwd=repo.repo_path,
                check=False,
                capture_output=True,
            )


def test_sweep_returns_zero_when_no_sandboxes(repo: GitService) -> None:
    assert repo.sweep_orphan_worktrees() == 0
