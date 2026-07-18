# tests/body/atomic/test_candidate_validate.py
"""Tests for the test.candidate_validate atomic action (#815).

test.candidate_validate exists to close two coupled defects in the sandboxed
flow.build_test_for_symbol path: PytestAcceptanceCondition used to write
`base_content + candidate` straight to the real target test path on every
generation iteration (rejected candidates included), via a `file_service` that
was not scoped to the sandbox worktree even when running inside one — leaking
candidates into the main repo tree and guaranteeing a propagate_changes
conflict. This action materializes each candidate under `var/tmp/` ephemeral
scratch instead, runs pytest there, and always cleans up — the real
target_path is never touched by candidate evaluation at all.

The action is @atomic_action-governed, so direct invocation goes through
`.__wrapped__` (mirrors tests/body/atomic/test_sandbox_validate.py).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.atomic.test_actions import action_test_candidate_validate
from body.infrastructure.storage.file_handler import FileHandler
from shared.action_types import ActionResult
from shared.context import CoreContext
from shared.infrastructure.git_service import GitService


_action = action_test_candidate_validate.__wrapped__


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Real git repo with an empty .intent/ (guard neutralized below)."""
    _run(["git", "init"], tmp_path)
    _run(["git", "config", "user.email", "exec@test.local"], tmp_path)
    _run(["git", "config", "user.name", "Exec Test"], tmp_path)
    _run(["git", "config", "commit.gpgsign", "false"], tmp_path)
    (tmp_path / ".intent").mkdir()
    (tmp_path / "scope.py").write_text("# original\n")
    _run(["git", "add", "-A"], tmp_path)
    _run(["git", "commit", "-m", "initial"], tmp_path)
    return tmp_path


def _make_context(repo: Path) -> CoreContext:
    file_handler = FileHandler(str(repo))
    # Unit-level: exercising the write/cleanup mechanics, not IntentGuard
    # governance — same neutralization as test_flow_sandbox_lifecycle.py.
    file_handler._guard_paths = lambda *a, **k: None  # type: ignore[method-assign]
    return CoreContext(
        registry=MagicMock(),
        git_service=GitService(repo),
        knowledge_service=MagicMock(),
        file_handler=file_handler,
        file_service=MagicMock(),
    )


async def test_candidate_never_written_to_target_path(repo: Path) -> None:
    """The real target test path must not exist after evaluation — candidate
    materialization only ever touches ephemeral scratch."""
    ctx = _make_context(repo)
    ok_result = ActionResult(action_id="test.candidate_validate", ok=True, data={})

    with patch(
        "body.atomic.test_actions.run_tests", new=AsyncMock(return_value=ok_result)
    ):
        result = await _action(
            source_file="src/x.py",
            target_path="tests/x/test_generated.py",
            candidate_content="def test_new():\n    assert True\n",
            core_context=ctx,
        )

    assert result.ok
    assert not (repo / "tests" / "x" / "test_generated.py").exists()
    assert not (repo / "tests").exists()  # never even creates the tests/ dir


async def test_scratch_directory_removed_after_success(repo: Path) -> None:
    ctx = _make_context(repo)
    ok_result = ActionResult(action_id="test.candidate_validate", ok=True, data={})

    with patch(
        "body.atomic.test_actions.run_tests", new=AsyncMock(return_value=ok_result)
    ):
        await _action(
            source_file="src/x.py",
            target_path="tests/x/test_generated.py",
            candidate_content="def test_new():\n    assert True\n",
            core_context=ctx,
        )

    scratch_root = repo / "var" / "tmp" / "candidate_validate"
    assert not scratch_root.exists() or not list(scratch_root.iterdir())


async def test_scratch_directory_removed_after_rejected_candidate(repo: Path) -> None:
    """Rejected candidates must leave no trace on disk anywhere — main tree or
    scratch — once evaluation completes."""
    ctx = _make_context(repo)
    failed_result = ActionResult(
        action_id="test.candidate_validate", ok=False, data={"summary": "1 failed"}
    )

    with patch(
        "body.atomic.test_actions.run_tests", new=AsyncMock(return_value=failed_result)
    ):
        result = await _action(
            source_file="src/x.py",
            target_path="tests/x/test_generated.py",
            candidate_content="def test_new():\n    assert False\n",
            core_context=ctx,
        )

    assert not result.ok
    assert result.data["violations"][0]["rule"] == "test.candidate.must_execute"
    scratch_root = repo / "var" / "tmp" / "candidate_validate"
    assert not scratch_root.exists() or not list(scratch_root.iterdir())
    assert not (repo / "tests").exists()


async def test_scratch_directory_removed_even_when_run_tests_raises(repo: Path) -> None:
    """Cleanup must happen via `finally` — an exception from run_tests must not
    leave scratch content behind."""
    ctx = _make_context(repo)

    with patch(
        "body.atomic.test_actions.run_tests",
        new=AsyncMock(side_effect=RuntimeError("subprocess exploded")),
    ):
        with pytest.raises(RuntimeError):
            await _action(
                source_file="src/x.py",
                target_path="tests/x/test_generated.py",
                candidate_content="def test_new():\n    assert True\n",
                core_context=ctx,
            )

    scratch_root = repo / "var" / "tmp" / "candidate_validate"
    assert not scratch_root.exists() or not list(scratch_root.iterdir())


async def test_run_tests_targets_scratch_path_not_real_target(repo: Path) -> None:
    ctx = _make_context(repo)
    ok_result = ActionResult(action_id="test.candidate_validate", ok=True, data={})
    mocked = AsyncMock(return_value=ok_result)

    with patch("body.atomic.test_actions.run_tests", new=mocked):
        await _action(
            source_file="src/x.py",
            target_path="tests/x/test_generated.py",
            candidate_content="def test_new():\n    assert True\n",
            core_context=ctx,
        )

    call_kwargs = mocked.call_args.kwargs
    assert call_kwargs["target"] != "tests/x/test_generated.py"
    assert "candidate_validate" in call_kwargs["target"]
    assert call_kwargs["target"].endswith("test_generated.py")
    assert Path(call_kwargs["repo_root"]) == repo


async def test_refuses_without_core_context() -> None:
    result = await _action(
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        candidate_content="def test_new(): assert True",
        core_context=None,
    )
    assert result.ok is False
    assert "core_context" in result.data["error"]
