# tests/body/atomic/test_sandbox_propagation_all_or_nothing.py
"""F3: a crash mid-propagation leaves the main tree exactly as it was.

Real git repositories: the sandbox changes three files, the main-tree write
of the second one fails, and the main tree must be byte-for-byte unchanged —
the first file restored (or, if it was new, absent along with any directory
the write created) and the third never written.
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
    (tmp_path / "b.py").write_text("b = 1\n")
    (tmp_path / "c.py").write_text("c = 1\n")
    (tmp_path / "m.py").write_text("m = 1\n")
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


def _snapshot(root: Path) -> dict[str, bytes | None]:
    """Every file and directory of the main tree, with its bytes. ``.git``
    and ``var/`` (where the sandbox worktree itself lives) are excluded."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
        for p in sorted(root.rglob("*"))
        if p.relative_to(root).parts[0] not in (".git", "var")
    }


def _fail_second_write(handler: FileHandler) -> list[str]:
    calls: list[str] = []
    real_write = handler.write

    def write(rel_path, content, **kwargs):
        calls.append(rel_path)
        if len(calls) == 2:
            raise OSError("disk full (injected) on the second file")
        return real_write(rel_path, content, **kwargs)

    handler.write = write  # type: ignore[method-assign]
    return calls


@pytest.mark.parametrize(
    "first",
    ["a.py", "a_new/pkg/a.py"],
    ids=["first-file-modified", "first-file-new-in-new-dir"],
)
# ID: 6d1c3e0a-5f47-4b8e-9a2c-7e1f0b3d9c41
def test_failure_on_second_of_three_files_leaves_main_tree_unchanged(
    repo: Path, first: str
) -> None:
    if first == "a.py":
        (repo / "a.py").write_text("a = 1\n")
        _run(["git", "add", "a.py"], repo)
        _run(["git", "commit", "-q", "-m", "add a"], repo)
    ctx = _context(repo)
    lifecycle = SandboxLifecycle(ctx)
    scoped_git = ctx.git_service.create_worktree(ctx.git_service.get_current_commit())
    sandbox = Path(scoped_git.repo_path)
    try:
        (sandbox / first).parent.mkdir(parents=True, exist_ok=True)
        (sandbox / first).write_text("a = 2\n")
        (sandbox / "b.py").write_text("b = 2\n")
        (sandbox / "c.py").write_text("c = 2\n")

        before = _snapshot(repo)
        calls = _fail_second_write(ctx.file_handler)
        with pytest.raises(OSError, match="second file"):
            lifecycle.propagate_changes(scoped_git)
    finally:
        scoped_git.cleanup()

    assert calls[:2] == [first, "b.py"]
    assert _snapshot(repo) == before
    assert not (repo / "a_new").exists()
    assert _run(["git", "status", "--porcelain"], repo) == ""


# ID: 2b9f4a71-0c8e-4d63-b5a1-9e7c3f2d8a06
def test_failure_after_a_deletion_restores_the_deleted_file(repo: Path) -> None:
    ctx = _context(repo)
    lifecycle = SandboxLifecycle(ctx)
    scoped_git = ctx.git_service.create_worktree(ctx.git_service.get_current_commit())
    sandbox = Path(scoped_git.repo_path)
    try:
        (sandbox / "b.py").unlink()
        (sandbox / "c.py").write_text("c = 2\n")
        (sandbox / "m.py").write_text("m = 2\n")
        _run(["git", "rm", "-q", "--cached", "b.py"], sandbox)

        before = _snapshot(repo)
        real_write = ctx.file_handler.write

        def write(rel_path, content, **kwargs):
            if rel_path == "m.py":
                raise OSError("injected failure on the third file")
            return real_write(rel_path, content, **kwargs)

        ctx.file_handler.write = write  # type: ignore[method-assign]
        with pytest.raises(OSError, match="third file"):
            lifecycle.propagate_changes(scoped_git, declared_deletions={"b.py"})
    finally:
        scoped_git.cleanup()

    assert _snapshot(repo) == before
    assert _run(["git", "status", "--porcelain"], repo) == ""
