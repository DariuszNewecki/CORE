# tests/will/phases/test_parse_phase_reconnaissance.py

"""ParsePhase feeds target reconnaissance into planning (#895 U1)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from shared.component_primitive import ComponentPhase, ComponentResult
from shared.models.refusal_result import RefusalResult
from will.phases.parse_phase import ParsePhase


class _StubGitService:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path


class _StubCoreContext:
    def __init__(self, repo_path: Path) -> None:
        self.git_service = _StubGitService(repo_path)
        self.cognitive_service = object()
        self.qdrant_service = None


class _StubWorkflowContext:
    def __init__(self, goal: str) -> None:
        self.goal = goal
        self.results: dict[str, Any] = {}


class _StubStep:
    """Minimal ExecutionTask stand-in: the phase logs .action and .step."""

    action = "check.imports"
    step = "inspect the target"


@dataclass
class _StubDecision:
    agent: str
    decision_type: str
    rationale: str
    chosen_action: str


class _StubTracer:
    def __init__(self) -> None:
        self.decisions = [
            _StubDecision(
                agent="PlannerAgent",
                decision_type="plan_created",
                rationale="target has no SQL corpus",
                chosen_action="check.imports",
            )
        ]


class _StubPlanner:
    """Records what the phase handed it."""

    def __init__(self) -> None:
        self.received_recon: str | None = None
        self.tracer = _StubTracer()

    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> list[object]:
        self.received_recon = reconnaissance_report
        return [_StubStep()]


class _StubRecon:
    def __init__(self, result: ComponentResult | Exception) -> None:
        self._result = result

    async def execute(self, repo_path: Path | str, **kwargs: Any) -> ComponentResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _recon_ok() -> ComponentResult:
    return ComponentResult(
        component_id="target_reconnaissance_analyzer",
        ok=True,
        data={
            "recon_text": "TARGET RECONNAISSANCE\n\nFiles observed: 3",
            "recon_raw": {"file_count": 3},
            "unavailable": [{"topic": "artifact_type:infra", "reason": "no match"}],
            "recon_digest": "596a2e3baeaf6c835ded22ce2106945bb2c3639e53c971aa2130fbf31376d86c",
        },
        phase=ComponentPhase.PARSE,
    )


def _phase(tmp_path: Path, recon: _StubRecon) -> tuple[ParsePhase, _StubPlanner]:
    phase = ParsePhase(_StubCoreContext(tmp_path))  # type: ignore[arg-type]
    planner = _StubPlanner()
    phase._planner = planner  # type: ignore[assignment]
    phase._recon = recon  # type: ignore[assignment]
    return phase, planner


@pytest.mark.asyncio
async def test_reconnaissance_report_reaches_the_planner(tmp_path: Path) -> None:
    phase, planner = _phase(tmp_path, _StubRecon(_recon_ok()))

    result = await phase.execute(_StubWorkflowContext("investigate the target"))

    assert result.ok is True
    assert planner.received_recon is not None
    assert "TARGET RECONNAISSANCE" in planner.received_recon


@pytest.mark.asyncio
async def test_plan_data_carries_the_reconnaissance_record(tmp_path: Path) -> None:
    phase, _ = _phase(tmp_path, _StubRecon(_recon_ok()))

    result = await phase.execute(_StubWorkflowContext("investigate the target"))

    recon = result.data["reconnaissance"]
    assert recon["available"] is True
    assert (
        recon["digest"]
        == "596a2e3baeaf6c835ded22ce2106945bb2c3639e53c971aa2130fbf31376d86c"
    )
    assert recon["unavailable"] == [
        {"topic": "artifact_type:infra", "reason": "no match"}
    ]


@pytest.mark.asyncio
async def test_a_refused_reconnaissance_does_not_fail_the_phase(tmp_path: Path) -> None:
    """Planning degrades to goal-only rather than stopping."""
    refusal = RefusalResult.boundary_violation(
        component_id="target_reconnaissance_analyzer",
        phase=ComponentPhase.PARSE,
        reason="target is not a readable directory",
        boundary="bound target root",
    )
    phase, planner = _phase(tmp_path, _StubRecon(refusal))

    result = await phase.execute(_StubWorkflowContext("investigate the target"))

    assert result.ok is True
    assert planner.received_recon == ""
    assert result.data["reconnaissance"]["available"] is False
    assert "not a readable directory" in result.data["reconnaissance"]["reason"]


@pytest.mark.asyncio
async def test_a_raising_reconnaissance_is_recorded_as_absent_not_empty(
    tmp_path: Path,
) -> None:
    """An empty report would claim the target is empty — a different, false statement."""
    phase, _ = _phase(tmp_path, _StubRecon(RuntimeError("walk exploded")))

    result = await phase.execute(_StubWorkflowContext("investigate the target"))

    assert result.ok is True
    recon = result.data["reconnaissance"]
    assert recon["available"] is False
    assert "walk exploded" in recon["reason"]


@pytest.mark.asyncio
async def test_planner_decisions_are_mirrored_into_plan_data(tmp_path: Path) -> None:
    """The tracer is never persisted, so the mirror is the only durable copy."""
    phase, _ = _phase(tmp_path, _StubRecon(_recon_ok()))

    result = await phase.execute(_StubWorkflowContext("investigate the target"))

    decisions = result.data["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["decision_type"] == "plan_created"
    assert decisions[0]["rationale"] == "target has no SQL corpus"


@pytest.mark.asyncio
async def test_a_planner_without_a_tracer_yields_no_decisions(tmp_path: Path) -> None:
    phase, planner = _phase(tmp_path, _StubRecon(_recon_ok()))
    planner.tracer = None  # type: ignore[assignment]

    result = await phase.execute(_StubWorkflowContext("investigate the target"))

    assert result.data["decisions"] == []
