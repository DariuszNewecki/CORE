# tests/will/phases/test_code_generation_split_planner.py
"""DeterministicSplitPlanner — extracted from CodeGenerationPhase (ADR-095).

Pins the delegation seam (refactor_modularity routes to the planner) and the
planner's LLM-free edges: JSON fence stripping, skipped/missing files, and the
"LLM produced no valid SplitPlan" outcome.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from shared.models.workflow_models import PhaseResult
from will.orchestration.workflow_orchestrator import WorkflowContext
from will.phases.code_generation.split_planner import DeterministicSplitPlanner
from will.phases.code_generation_phase import CodeGenerationPhase


def _planner(repo: Path) -> DeterministicSplitPlanner:
    core_context = MagicMock()
    core_context.git_service.repo_path = repo
    return DeterministicSplitPlanner(core_context)


def _context(*file_paths: str) -> WorkflowContext:
    context = WorkflowContext(
        goal="g", workflow_type="refactor_modularity", write=False
    )
    context.results["planning"] = {
        "execution_plan": [
            SimpleNamespace(params=SimpleNamespace(file_path=fp)) for fp in file_paths
        ]
    }
    return context


def test_extract_json_strips_fences() -> None:
    raw = '```json\n{"a": 1}\n```'
    assert DeterministicSplitPlanner._extract_json(raw) == '{"a": 1}'
    assert DeterministicSplitPlanner._extract_json('  {"a": 1}  ') == '{"a": 1}'


async def test_missing_source_file_is_skipped(tmp_path: Path) -> None:
    result = await _planner(tmp_path).execute(_context("src/nope.py"), 0.0)
    assert result.ok is False
    assert result.data == {"deterministic_split": True, "split_results": []}


async def test_invalid_split_plan_is_reported(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("def a():\n    pass\n", encoding="utf-8")
    planner = _planner(tmp_path)
    with patch.object(planner, "_request_split_plan", new=AsyncMock(return_value=None)):
        result = await planner.execute(_context("m.py"), 0.0)
    assert result.ok is False
    assert result.data["split_results"] == [
        {
            "file": "m.py",
            "ok": False,
            "error": "LLM failed to produce a valid SplitPlan",
        }
    ]


async def test_phase_delegates_refactor_modularity_to_planner(tmp_path: Path) -> None:
    core_context = MagicMock()
    core_context.git_service.repo_path = tmp_path
    with (
        patch("will.phases.code_generation_phase.DecisionTracer"),
        patch("will.phases.code_generation_phase.PytestSandboxRunner"),
    ):
        phase = CodeGenerationPhase(core_context)
    assert isinstance(phase.split_planner, DeterministicSplitPlanner)
    sentinel = PhaseResult(name="code_generation", ok=True)
    context = _context("m.py")
    with patch.object(
        phase.split_planner, "execute", new=AsyncMock(return_value=sentinel)
    ) as delegated:
        result = await phase.execute(context)
    assert result is sentinel
    delegated.assert_awaited_once()
    assert delegated.await_args.args[0] is context
