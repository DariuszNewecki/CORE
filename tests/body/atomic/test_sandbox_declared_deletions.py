# tests/body/atomic/test_sandbox_declared_deletions.py
"""Deletions carried from sandbox to main tree to commit (ADR-168 Amendment
2026-10-10 A3; producer build U4).

Real git repositories throughout: an approved patch's deletions used to be
dropped at copy-back, so the commit silently lost them. A deletion now
propagates only when the action declared it.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from body.atomic.assisted_actions import action_assisted_apply_diff
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
    (tmp_path / "keep.py").write_text("x = 1\n")
    (tmp_path / "gone.py").write_text("y = 1\n")
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


_PATCH = (
    "diff --git a/gone.py b/gone.py\n"
    "deleted file mode 100644\n"
    "--- a/gone.py\n"
    "+++ /dev/null\n"
    "@@ -1 +0,0 @@\n"
    "-y = 1\n"
    "diff --git a/keep.py b/keep.py\n"
    "--- a/keep.py\n"
    "+++ b/keep.py\n"
    "@@ -1 +1 @@\n"
    "-x = 1\n"
    "+x = 2\n"
)


async def _apply_in_sandbox(repo: Path) -> tuple[SandboxLifecycle, object, dict]:
    ctx = _context(repo)
    lifecycle = SandboxLifecycle(ctx)
    scoped_git = ctx.git_service.create_worktree(ctx.git_service.get_current_commit())
    scoped_ctx = _context(Path(scoped_git.repo_path))
    result = await action_assisted_apply_diff.__wrapped__(
        patch=_PATCH,
        patch_digest=hashlib.sha256(_PATCH.encode()).hexdigest(),
        validated_base_sha=scoped_ctx.git_service.get_current_commit(),
        core_context=scoped_ctx,
    )
    assert result.ok, result.data
    return lifecycle, scoped_git, result.data


# ID: f0c6f63c-4ba4-4b4e-bea8-a651fade9c66
async def test_apply_diff_declares_the_patch_deletions(repo: Path) -> None:
    _, scoped_git, data = await _apply_in_sandbox(repo)
    try:
        assert data["declared_deletions"] == ["gone.py"]
    finally:
        scoped_git.cleanup()


# ID: 4058f89e-42c3-4a38-99e7-1d487f2d3038
async def test_declared_deletion_reaches_main_tree_and_commit(repo: Path) -> None:
    lifecycle, scoped_git, data = await _apply_in_sandbox(repo)
    try:
        produced = lifecycle.propagate_changes(
            scoped_git, declared_deletions=set(data["declared_deletions"])
        )
    finally:
        scoped_git.cleanup()

    assert produced == {"gone.py", "keep.py"}
    assert not (repo / "gone.py").exists()
    assert (repo / "keep.py").read_text() == "x = 2\n"

    GitService(repo).commit_paths(sorted(produced), "apply approved patch")
    status = _run(["git", "show", "--name-status", "--format=", "HEAD"], repo)
    assert sorted(status.split()) == sorted(["D", "gone.py", "M", "keep.py"])


# ID: 09bff0d2-85fd-463e-b668-4e6853285475
async def test_undeclared_deletion_is_still_skipped(repo: Path) -> None:
    lifecycle, scoped_git, _ = await _apply_in_sandbox(repo)
    try:
        produced = lifecycle.propagate_changes(scoped_git)
    finally:
        scoped_git.cleanup()

    assert produced == {"keep.py"}
    assert (repo / "gone.py").read_text() == "y = 1\n"


# ID: dc0ebaa9-64d8-4f7c-b595-4f05fae1d398
async def test_deletion_refused_when_main_has_an_edit_on_that_file(repo: Path) -> None:
    lifecycle, scoped_git, data = await _apply_in_sandbox(repo)
    (repo / "gone.py").write_text("y = 99  # governor edit\n")
    try:
        with pytest.raises(RuntimeError, match="uncommitted changes"):
            lifecycle.propagate_changes(
                scoped_git, declared_deletions=set(data["declared_deletions"])
            )
    finally:
        scoped_git.cleanup()
    assert (repo / "gone.py").read_text() == "y = 99  # governor edit\n"


# ID: a987a372-c1f4-4f21-a5f6-52841c45e434
async def test_apply_in_a_vanished_sandbox_fails_instead_of_reporting_success(
    repo: Path,
) -> None:
    """The da93593b race: the sandbox was swept mid-action; git found the
    enclosing repository, `git apply` ignored the patch and exited 0."""
    ctx = _context(repo)
    scoped_git = ctx.git_service.create_worktree(ctx.git_service.get_current_commit())
    scoped_ctx = _context(Path(scoped_git.repo_path))
    sha = scoped_ctx.git_service.get_current_commit()
    (Path(scoped_git.repo_path) / ".git").unlink()
    try:
        result = await action_assisted_apply_diff.__wrapped__(
            patch=_PATCH,
            patch_digest=hashlib.sha256(_PATCH.encode()).hexdigest(),
            validated_base_sha=sha,
            core_context=scoped_ctx,
        )
    finally:
        import shutil

        shutil.rmtree(scoped_git.repo_path, ignore_errors=True)
        _run(["git", "worktree", "prune"], repo)

    assert result.ok is False
    assert (repo / "keep.py").read_text() == "x = 1\n"
