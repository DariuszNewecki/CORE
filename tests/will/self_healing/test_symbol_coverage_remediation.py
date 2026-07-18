# tests/will/self_healing/test_symbol_coverage_remediation.py
"""Tests for the symbol-granular coverage remediation orchestrator (#814).

No unit tests existed for the call chain this replaces
(EnhancedTestGenerator / EnhancedSingleFileRemediationService /
BatchRemediationService) prior to this file — confirmed during #814
reconnaissance. Mocks at the seam of each governed primitive
(TestGapEvaluator, SandboxLifecycle, TestGenCognitiveDelegate, FlowExecutor)
so these tests exercise the orchestration logic itself, not the primitives'
own internals (each of those has — or, per #815, now has — its own coverage).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from body.flows.result import FlowResult, StepResult
from shared.component_primitive import ComponentPhase, ComponentResult
from will.self_healing.symbol_coverage_remediation import (
    remediate_batch_by_symbol,
    remediate_file_by_symbol,
)


def _gap_result(gaps: list[dict], test_file: str = "tests/x/test_thing.py") -> ComponentResult:
    return ComponentResult(
        component_id="test_gap_evaluator",
        ok=True,
        data={
            "source_file": "src/x/thing.py",
            "test_file": test_file,
            "test_file_exists": True,
            "gaps": gaps,
            "already_covered": [],
            "gap_count": len(gaps),
            "covered_count": 0,
        },
        phase=ComponentPhase.AUDIT,
        confidence=1.0,
    )


def _make_context(tmp_path: Path) -> MagicMock:
    (tmp_path / "src" / "x").mkdir(parents=True)
    (tmp_path / "src" / "x" / "thing.py").write_text("def do_work(): pass\n")

    git_service = MagicMock()
    git_service.repo_path = tmp_path
    git_service.get_current_commit.return_value = "deadbeef"

    context = MagicMock()
    context.git_service = git_service
    return context


def _flow_result(ok: bool, symbol_name: str, test_file: str = "tests/x/test_thing.py") -> FlowResult:
    if ok:
        steps = [
            StepResult(
                ref_id="build.test_for_symbol",
                required=True,
                ok=True,
                data={"test_file": test_file, "files_produced": [test_file]},
            )
        ]
    else:
        steps = [
            StepResult(
                ref_id="generate.test_snippet",
                required=True,
                ok=False,
                data={"error": f"generation failed for {symbol_name}"},
            )
        ]
    return FlowResult(flow_id="flow.build_test_for_symbol", ok=ok, steps=steps)


_MODULE = "will.self_healing.symbol_coverage_remediation"


async def test_write_false_rejected_without_any_io(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    with patch(f"{_MODULE}.TestGapEvaluator") as gap_eval:
        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=False)

    assert result["status"] == "failed"
    assert "write=false" in result["error"]
    gap_eval.assert_not_called()


async def test_missing_source_file_rejected(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    result = await remediate_file_by_symbol(context, "src/x/does_not_exist.py", write=True)
    assert result["status"] == "failed"
    assert "does not exist" in result["error"]


async def test_zero_gaps_skips_worktree_entirely(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    evaluator_instance = AsyncMock()
    evaluator_instance.execute = AsyncMock(return_value=_gap_result([]))

    with (
        patch(f"{_MODULE}.TestGapEvaluator", return_value=evaluator_instance),
        patch(f"{_MODULE}.SandboxLifecycle") as sandbox_cls,
    ):
        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=True)

    assert result["status"] == "completed"
    assert result["summary"] == {"gaps": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    sandbox_cls.assert_not_called()


async def test_gap_evaluator_failure_returns_failed_status(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    bad_result = ComponentResult(
        component_id="test_gap_evaluator",
        ok=False,
        data={"error": "Syntax error in source"},
        phase=ComponentPhase.AUDIT,
        confidence=0.0,
    )
    evaluator_instance = AsyncMock()
    evaluator_instance.execute = AsyncMock(return_value=bad_result)

    with patch(f"{_MODULE}.TestGapEvaluator", return_value=evaluator_instance):
        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=True)

    assert result["status"] == "failed"
    assert "Syntax error" in result["error"]


async def test_single_symbol_success_propagates_declared_production(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    gap = {"name": "do_work", "kind": "function", "signature": "def do_work()"}
    evaluator_instance = AsyncMock()
    evaluator_instance.execute = AsyncMock(return_value=_gap_result([gap]))

    scoped_git = MagicMock()
    flow_executor_instance = AsyncMock()
    flow_executor_instance.execute = AsyncMock(
        return_value=_flow_result(True, "do_work")
    )

    with (
        patch(f"{_MODULE}.TestGapEvaluator", return_value=evaluator_instance),
        patch(f"{_MODULE}.SandboxLifecycle") as sandbox_cls,
        patch(f"{_MODULE}.TestGenCognitiveDelegate", return_value=MagicMock()),
        patch(f"{_MODULE}.FlowExecutor", return_value=flow_executor_instance),
    ):
        sandbox_instance = MagicMock()
        sandbox_instance.build_flow_execution_context.return_value = (
            MagicMock(),
            scoped_git,
        )
        sandbox_instance.propagate_changes.return_value = {"tests/x/test_thing.py"}
        sandbox_cls.return_value = sandbox_instance

        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=True)

    assert result["status"] == "completed"
    assert result["summary"] == {"gaps": 1, "succeeded": 1, "failed": 0, "skipped": 0}
    assert result["files_produced"] == ["tests/x/test_thing.py"]
    sandbox_instance.propagate_changes.assert_called_once_with(
        scoped_git, only_paths={"tests/x/test_thing.py"}
    )
    scoped_git.cleanup.assert_called_once()


async def test_partial_failure_within_file_continues_remaining_symbols(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    gaps = [
        {"name": "do_work", "kind": "function", "signature": "def do_work()"},
        {"name": "do_other", "kind": "function", "signature": "def do_other()"},
    ]
    evaluator_instance = AsyncMock()
    evaluator_instance.execute = AsyncMock(return_value=_gap_result(gaps))

    scoped_git = MagicMock()
    flow_executor_instance = AsyncMock()
    flow_executor_instance.execute = AsyncMock(
        side_effect=[
            _flow_result(True, "do_work"),
            _flow_result(False, "do_other"),
        ]
    )

    with (
        patch(f"{_MODULE}.TestGapEvaluator", return_value=evaluator_instance),
        patch(f"{_MODULE}.SandboxLifecycle") as sandbox_cls,
        patch(f"{_MODULE}.TestGenCognitiveDelegate", return_value=MagicMock()),
        patch(f"{_MODULE}.FlowExecutor", return_value=flow_executor_instance),
    ):
        sandbox_instance = MagicMock()
        sandbox_instance.build_flow_execution_context.return_value = (
            MagicMock(),
            scoped_git,
        )
        sandbox_instance.propagate_changes.return_value = {"tests/x/test_thing.py"}
        sandbox_cls.return_value = sandbox_instance

        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=True)

    assert result["status"] == "completed"
    assert result["summary"] == {"gaps": 2, "succeeded": 1, "failed": 1, "skipped": 0}
    assert flow_executor_instance.execute.call_count == 2
    assert result["results"][1]["ok"] is False
    assert "generation failed for do_other" in result["results"][1]["error"]
    # Only the successful symbol's declared production propagates.
    sandbox_instance.propagate_changes.assert_called_once_with(
        scoped_git, only_paths={"tests/x/test_thing.py"}
    )
    scoped_git.cleanup.assert_called_once()


async def test_sandbox_creation_failure_returns_error_status(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    gap = {"name": "do_work", "kind": "function", "signature": "def do_work()"}
    evaluator_instance = AsyncMock()
    evaluator_instance.execute = AsyncMock(return_value=_gap_result([gap]))

    with (
        patch(f"{_MODULE}.TestGapEvaluator", return_value=evaluator_instance),
        patch(f"{_MODULE}.SandboxLifecycle") as sandbox_cls,
    ):
        sandbox_instance = MagicMock()
        sandbox_instance.build_flow_execution_context.return_value = (MagicMock(), None)
        sandbox_cls.return_value = sandbox_instance

        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=True)

    assert result["status"] == "error"
    assert "did not sandbox" in result["error"]


async def test_exception_mid_flow_still_cleans_up_worktree(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    gap = {"name": "do_work", "kind": "function", "signature": "def do_work()"}
    evaluator_instance = AsyncMock()
    evaluator_instance.execute = AsyncMock(return_value=_gap_result([gap]))

    scoped_git = MagicMock()
    flow_executor_instance = AsyncMock()
    flow_executor_instance.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch(f"{_MODULE}.TestGapEvaluator", return_value=evaluator_instance),
        patch(f"{_MODULE}.SandboxLifecycle") as sandbox_cls,
        patch(f"{_MODULE}.TestGenCognitiveDelegate", return_value=MagicMock()),
        patch(f"{_MODULE}.FlowExecutor", return_value=flow_executor_instance),
    ):
        sandbox_instance = MagicMock()
        sandbox_instance.build_flow_execution_context.return_value = (
            MagicMock(),
            scoped_git,
        )
        sandbox_cls.return_value = sandbox_instance

        result = await remediate_file_by_symbol(context, "src/x/thing.py", write=True)

    assert result["status"] == "error"
    assert "boom" in result["error"]
    scoped_git.cleanup.assert_called_once()


async def test_batch_write_false_rejected_before_selection(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    with patch(f"{_MODULE}.select_batch_candidates") as selector:
        result = await remediate_batch_by_symbol(context, write=False)

    assert result["status"] == "failed"
    selector.assert_not_called()


async def test_batch_no_candidates(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    with patch(f"{_MODULE}.select_batch_candidates", return_value=[]):
        result = await remediate_batch_by_symbol(context, write=True)

    assert result["status"] == "no_candidates"
    assert result["summary"] == {"success": 0, "failed": 0, "skipped": 0}


async def test_batch_one_file_error_does_not_sink_others(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    file_a = tmp_path / "src" / "a.py"
    file_b = tmp_path / "src" / "b.py"

    async def fake_remediate(ctx, source_file, *, write):
        if source_file.endswith("a.py"):
            return {"status": "error", "source_file": source_file, "error": "boom"}
        return {
            "status": "completed",
            "source_file": source_file,
            "test_file": "tests/test_b.py",
            "summary": {"gaps": 1, "succeeded": 1, "failed": 0, "skipped": 0},
            "results": [],
            "files_produced": ["tests/test_b.py"],
        }

    with (
        patch(
            f"{_MODULE}.select_batch_candidates",
            return_value=[(file_a, 10.0), (file_b, 20.0)],
        ),
        patch(f"{_MODULE}.remediate_file_by_symbol", side_effect=fake_remediate),
    ):
        result = await remediate_batch_by_symbol(context, write=True, count=5)

    assert result["status"] == "completed"
    assert result["processed"] == 2
    assert result["summary"] == {"success": 1, "failed": 1, "skipped": 0}


async def test_batch_skipped_counts_zero_gap_files_separately(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    file_a = tmp_path / "src" / "a.py"

    async def fake_remediate(ctx, source_file, *, write):
        return {
            "status": "completed",
            "source_file": source_file,
            "test_file": "tests/test_a.py",
            "summary": {"gaps": 0, "succeeded": 0, "failed": 0, "skipped": 0},
            "results": [],
            "files_produced": [],
        }

    with (
        patch(f"{_MODULE}.select_batch_candidates", return_value=[(file_a, 10.0)]),
        patch(f"{_MODULE}.remediate_file_by_symbol", side_effect=fake_remediate),
    ):
        result = await remediate_batch_by_symbol(context, write=True)

    assert result["summary"] == {"success": 0, "failed": 0, "skipped": 1}
