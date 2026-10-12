# tests/body/atomic/test_candidate_validate.py
"""Tests for the test.candidate_validate atomic action (#815).

test.candidate_validate exists to close two coupled defects in the sandboxed
flow.build_test_for_symbol path: PytestAcceptanceCondition used to write
`base_content + candidate` straight to the real target test path on every
generation iteration (rejected candidates included), via a `file_service` that
was not scoped to the sandbox worktree even when running inside one — leaking
candidates into the main repo tree and guaranteeing a propagate_changes
conflict. This action adds each candidate to the sandbox's copy of the
repository only (an overlay under `var/tmp/candidate_validate/`) and runs
pytest there; nothing is written to disk, so the real target_path is never
touched by candidate evaluation at all.

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
    # The candidate reaches the sandbox as an overlay at the target it runs.
    assert call_kwargs["overlay"] == (
        (call_kwargs["target"], b"def test_new():\n    assert True\n"),
    )


async def test_refuses_without_core_context() -> None:
    result = await _action(
        source_file="src/x.py",
        target_path="tests/x/test_generated.py",
        candidate_content="def test_new(): assert True",
        core_context=None,
    )
    assert result.ok is False
    assert "core_context" in result.data["error"]


# --- sibling check: a candidate must not break the existing tests for its module


def _result(ok: bool, summary: str = "") -> ActionResult:
    return ActionResult(
        action_id="test.candidate_validate", ok=ok, data={"summary": summary}
    )


async def _run_with_siblings(repo: Path, run_results: list[ActionResult]):
    mocked = AsyncMock(side_effect=run_results)
    with (
        patch("body.atomic.test_actions.run_tests", new=mocked),
        patch(
            "body.atomic.test_actions.sibling_test_paths",
            return_value=["tests/x_test_x.py"],
        ),
    ):
        result = await _action(
            source_file="src/x.py",
            target_path="tests/x/test_generated.py",
            candidate_content="def test_new():\n    assert True\n",
            core_context=_make_context(repo),
        )
    return result, mocked


async def test_candidate_leaking_state_into_siblings_is_rejected(repo: Path) -> None:
    """Solo pass, combined fail, siblings alone pass -> the candidate broke them."""
    result, mocked = await _run_with_siblings(
        repo, [_result(True), _result(False, "1 failed, 3 passed"), _result(True)]
    )

    assert not result.ok
    assert "leaks shared state" in result.data["error"]
    assert result.data["sibling_tests"] == ["tests/x_test_x.py"]
    assert result.data["violations"][0]["rule"] == "test.candidate.must_execute"
    combined_call = mocked.call_args_list[1].kwargs
    assert "candidate_validate" in combined_call["target"]
    assert combined_call["extra_targets"] == ["tests/x_test_x.py"]
    assert combined_call["overlay"][0][0] == combined_call["target"]


async def test_candidate_not_blamed_when_siblings_already_fail(repo: Path) -> None:
    result, mocked = await _run_with_siblings(
        repo, [_result(True), _result(False), _result(False)]
    )

    assert result.ok
    assert result.data["sibling_baseline_failing"] == ["tests/x_test_x.py"]
    assert mocked.await_count == 3


async def test_candidate_passing_with_siblings_is_accepted(repo: Path) -> None:
    result, mocked = await _run_with_siblings(repo, [_result(True), _result(True)])

    assert result.ok
    assert mocked.await_count == 2


async def test_rejected_solo_candidate_skips_sibling_run(repo: Path) -> None:
    result, mocked = await _run_with_siblings(repo, [_result(False, "1 failed")])

    assert not result.ok
    assert mocked.await_count == 1


# --- real sandbox run (local mode): the candidate must reach the sandbox copy


@pytest.fixture
def code_repo(repo: Path) -> Path:
    (repo / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n', encoding="utf-8"
    )
    (repo / "src" / "mymod").mkdir(parents=True)
    (repo / "src" / "mymod" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "mymod" / "example.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8"
    )
    return repo


async def _validate_in_local_sandbox(
    repo: Path, monkeypatch: pytest.MonkeyPatch, candidate: str
) -> ActionResult:
    monkeypatch.setenv("CORE_SANDBOX_MODE", "local")
    with (
        patch(
            "shared.infrastructure.bootstrap_registry.BootstrapRegistry.get_repo_path",
            return_value=repo,
        ),
        patch("body.sandbox.repo_tests._persist_result_to_db", new=AsyncMock()),
    ):
        return await _action(
            source_file="src/mymod/example.py",
            target_path="tests/mymod/example/test_generated.py",
            candidate_content=candidate,
            core_context=_make_context(repo),
        )


async def test_passing_candidate_runs_in_the_sandbox_and_is_accepted(
    code_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sandbox copies no var/; the candidate reaches it as an overlay."""
    result = await _validate_in_local_sandbox(
        code_repo,
        monkeypatch,
        "from mymod.example import add\n\n\ndef test_add() -> None:\n"
        "    assert add(1, 2) == 3\n",
    )

    assert result.ok, result.data.get("summary")
    assert result.data["counts"].get("passed") == 1
    assert not (code_repo / "tests").exists()


async def test_failing_candidate_is_rejected_by_the_sandbox_run(
    code_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = await _validate_in_local_sandbox(
        code_repo,
        monkeypatch,
        "from mymod.example import add\n\n\ndef test_add() -> None:\n"
        "    assert add(1, 2) == 4\n",
    )

    assert not result.ok
    assert result.data["counts"].get("failed") == 1
