# tests/body/atomic/test_sandbox_main_moved.py
"""Copy-back refuses when the main tree moved under a target file.

Real git repositories throughout. The copy writes whole files built on the
sandbox's base commit, so a commit that landed on the main tree after the
sandbox was created, on a file the sandbox also changed, would be silently
undone; a clean main tree did not catch it (external review of the ADR-132
D10 D2 design, point 4, 2026-10-11).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from body.atomic.sandbox_lifecycle import SandboxLifecycle
from body.infrastructure.storage.file_handler import FileHandler
from shared.context import CoreContext
from shared.infrastructure.git_service import GitService


def _run(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _run(["git", "init", "-q"], tmp_path)
    _run(["git", "config", "user.email", "t@t.invalid"], tmp_path)
    _run(["git", "config", "user.name", "t"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / ".intent").mkdir()
    (tmp_path / "target.py").write_text("a = 1\nb = 1\n")
    (tmp_path / "other.py").write_text("z = 1\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-q", "-m", "base"], tmp_path)
    return tmp_path


def _context(root: Path) -> CoreContext:
    handler = FileHandler(str(root))
    # Copy-back mechanics, not IntentGuard: the bare repo has no law.
    handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    return CoreContext(
        registry=MagicMock(),
        git_service=GitService(root),
        knowledge_service=MagicMock(),
        file_handler=handler,
        file_service=MagicMock(),
    )


def _sandbox_edits_target(repo: Path) -> tuple[SandboxLifecycle, object]:
    ctx = _context(repo)
    scoped_git = ctx.git_service.create_worktree(ctx.git_service.get_current_commit())
    (Path(scoped_git.repo_path) / "target.py").write_text("a = 2\nb = 1\n")
    return SandboxLifecycle(ctx), scoped_git


def _commit_on_main(repo: Path, rel: str, content: str) -> None:
    (repo / rel).write_text(content)
    _run(["git", "commit", "-q", "-am", f"main edits {rel}"], repo)


# ID: 29373f90-7203-4ebd-90f3-29a905329aa1
def test_refuses_when_a_main_commit_touched_a_target_file(repo: Path) -> None:
    lifecycle, scoped_git = _sandbox_edits_target(repo)
    _commit_on_main(repo, "target.py", "a = 1\nb = 2\n")
    try:
        with pytest.raises(RuntimeError, match="main tree moved"):
            lifecycle.propagate_changes(scoped_git)
    finally:
        scoped_git.cleanup()
    # The intervening commit survives; nothing was copied over it.
    assert (repo / "target.py").read_text() == "a = 1\nb = 2\n"
    assert _run(["git", "status", "--porcelain"], repo) == ""


# ID: 0f257b42-4ef7-477a-bbe1-9b283d63a62d
def test_propagates_when_main_moved_only_on_other_files(repo: Path) -> None:
    lifecycle, scoped_git = _sandbox_edits_target(repo)
    _commit_on_main(repo, "other.py", "z = 2\n")
    try:
        produced = lifecycle.propagate_changes(scoped_git)
    finally:
        scoped_git.cleanup()
    assert produced == {"target.py"}
    assert (repo / "target.py").read_text() == "a = 2\nb = 1\n"
    assert (repo / "other.py").read_text() == "z = 2\n"


# ID: 2e547ed4-703a-44e2-b97d-4cbb124d9d2f
def test_refuses_when_the_commit_range_cannot_be_read(repo: Path) -> None:
    lifecycle, scoped_git = _sandbox_edits_target(repo)
    _commit_on_main(repo, "other.py", "z = 2\n")
    git = lifecycle.core_context.git_service
    git.commits_between = MagicMock(side_effect=RuntimeError("bad revision"))  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="cannot compare"):
            lifecycle.propagate_changes(scoped_git)
    finally:
        scoped_git.cleanup()
    assert (repo / "target.py").read_text() == "a = 1\nb = 1\n"
