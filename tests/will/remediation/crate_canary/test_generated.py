from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from body.infrastructure.storage.file_handler import FileOpResult
from will.remediation.crate_canary import CrateCanaryMixin


# ID: 91c87a42-fc5f-42fc-995a-7515d01ed5f9
class ConcreteCrateCanaryMixin(CrateCanaryMixin):
    """Concrete subclass to test the mixin."""

    def __init__(self):
        self._ctx = MagicMock()
        self._target_rule = "test-rule"


@pytest.mark.asyncio
# ID: 80a3a112-2369-4c2d-abf2-5c5855f530d3
async def test_CrateCanaryMixin():
    mixin = ConcreteCrateCanaryMixin()
    mock_action_executor = AsyncMock()
    mock_action_executor.execute.return_value = MagicMock(
        ok=True, data={"crate_id": "crate-123"}
    )
    mixin._ctx.action_executor = mock_action_executor

    # _pack_crate happy path
    result = await mixin._pack_crate("test.py", "fixed source")
    assert result == "crate-123"
    mock_action_executor.execute.assert_awaited_once_with(
        "crate.create",
        write=True,
        intent="Fix test-rule violations in test.py via autonomous remediation",
        payload_files={"test.py": "fixed source"},
    )


# --- _generate_patch (ADR-154 D1) ---


def _init_git_repo(path: Path, file_path: str, content: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    target = path / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", file_path], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=path, check=True)


def _stage_crate_file(
    repo_root: Path, crate_id: str, file_path: str, content: str
) -> None:
    staged = repo_root / "var" / "workflows" / "crates" / "inbox" / crate_id / file_path
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text(content, encoding="utf-8")


def _wire_real_file_handler(mixin: ConcreteCrateCanaryMixin, repo_root: Path) -> None:
    """_generate_patch routes its worktree write through FileHandler
    (governance.mutation_surface.filehandler_required) — stand in a mock
    that performs a REAL write and returns success, so the byte-equivalence
    assertions below still exercise a real on-disk write, not a no-op mock."""
    repo_root.mkdir(parents=True, exist_ok=True)

    def _write_runtime_text(rel_path: str, content: str) -> FileOpResult:
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return FileOpResult("success", "Wrote runtime text", rel_path)

    file_handler = MagicMock()
    file_handler.repo_path = repo_root
    file_handler.write_runtime_text.side_effect = _write_runtime_text
    mixin._ctx.file_handler = file_handler


def _init_bare_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _git_apply(repo_dir: Path, patch_text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "apply", "--whitespace=nowarn"],
        cwd=repo_dir,
        input=patch_text,
        text=True,
        capture_output=True,
    )


@pytest.mark.asyncio
# ID: 3e9d6a0b-2c9d-49a2-8f6a-5f2c2e5b9d0e
async def test_generate_patch_reproduces_aligned_bytes_via_git_apply(tmp_path) -> None:
    """Byte-equivalence proof (ADR-154 D1): applying the generated patch to a
    fresh checkout at baseline reproduces exactly the staged aligned bytes —
    not an approximation reconstructed from the raw LLM output."""
    file_path = "pkg/mod.py"
    original = "x = 1\n"
    aligned = "x = 2\n"

    repo_root = tmp_path / "repo"
    _stage_crate_file(repo_root, "crate-1", file_path, aligned)

    # Nested under repo_root/var/tmp/ — matching GitService.create_worktree's
    # real topology (PathResolver(repo_path).tmp_dir), since _generate_patch
    # now resolves its write target relative to file_handler.repo_path.
    worktree_dir = repo_root / "var" / "tmp" / "worktree-sandbox"
    _init_git_repo(worktree_dir, file_path, original)

    mixin = ConcreteCrateCanaryMixin()
    _wire_real_file_handler(mixin, repo_root)
    mixin._ctx.git_service.repo_path = repo_root
    worktree_mock = MagicMock()
    worktree_mock.repo_path = str(worktree_dir)
    mixin._ctx.git_service.create_worktree.return_value = worktree_mock

    patch_text = await mixin._generate_patch(file_path, "crate-1", "baseline-sha")

    assert patch_text
    mixin._ctx.git_service.create_worktree.assert_called_once_with("baseline-sha")
    worktree_mock.cleanup.assert_called_once()

    apply_dir = tmp_path / "apply-target"
    _init_git_repo(apply_dir, file_path, original)
    result = _git_apply(apply_dir, patch_text)
    assert result.returncode == 0, result.stderr
    assert (apply_dir / file_path).read_text(encoding="utf-8") == aligned


@pytest.mark.asyncio
# ID: 6a2b8e4f-7c1d-4e9a-9b3f-1d8c6a4e2f0b
async def test_generate_patch_empty_diff_returns_none(tmp_path) -> None:
    """No byte change (aligned == baseline) must yield an empty diff, and the
    method must surface that as None — never a falsely 'successful' patch."""
    file_path = "pkg/mod.py"
    same = "x = 1\n"

    repo_root = tmp_path / "repo"
    _stage_crate_file(repo_root, "crate-1", file_path, same)

    worktree_dir = repo_root / "var" / "tmp" / "worktree-sandbox"
    _init_git_repo(worktree_dir, file_path, same)

    mixin = ConcreteCrateCanaryMixin()
    _wire_real_file_handler(mixin, repo_root)
    mixin._ctx.git_service.repo_path = repo_root
    worktree_mock = MagicMock()
    worktree_mock.repo_path = str(worktree_dir)
    mixin._ctx.git_service.create_worktree.return_value = worktree_mock

    patch_text = await mixin._generate_patch(file_path, "crate-1", "baseline-sha")

    assert patch_text is None
    worktree_mock.cleanup.assert_called_once()


@pytest.mark.asyncio
# ID: 9c4f1a8e-3b7d-4a6c-8e2f-0d5a9c1b7e3f
async def test_generate_patch_missing_staged_file_returns_none(tmp_path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    mixin = ConcreteCrateCanaryMixin()
    mixin._ctx.git_service.repo_path = repo_root

    patch_text = await mixin._generate_patch("pkg/mod.py", "crate-missing", "sha")

    assert patch_text is None
    mixin._ctx.git_service.create_worktree.assert_not_called()


@pytest.mark.asyncio
# ID: 1f6d8b2a-4e9c-4b3f-9a7d-2c5e8f0a6b4d
async def test_generate_patch_missing_baseline_file_returns_none(tmp_path) -> None:
    """The staged file exists but the target path is absent at *baseline_sha*
    in the worktree — must fail closed, not diff against a nonexistent
    baseline."""
    file_path = "pkg/mod.py"
    repo_root = tmp_path / "repo"
    _stage_crate_file(repo_root, "crate-1", file_path, "x = 2\n")

    worktree_dir = tmp_path / "worktree"
    _init_bare_git_repo(worktree_dir)

    mixin = ConcreteCrateCanaryMixin()
    mixin._ctx.git_service.repo_path = repo_root
    worktree_mock = MagicMock()
    worktree_mock.repo_path = str(worktree_dir)
    mixin._ctx.git_service.create_worktree.return_value = worktree_mock

    patch_text = await mixin._generate_patch(file_path, "crate-1", "baseline-sha")

    assert patch_text is None
    worktree_mock.cleanup.assert_called_once()
