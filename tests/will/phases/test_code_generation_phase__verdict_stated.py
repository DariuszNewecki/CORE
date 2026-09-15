"""A partial code-generation result STATES its verdict (#894 seeded live run).

`CodeGenerationPhase.execute` returns ok=False when fewer than 80% of steps
generated, but carried the reason only in `data` (success_rate, counts). The
Worker's outcome record keeps a phase's name/ok/error, so the exported run
read "code_generation failed: None" -- a model verdict with no stated cause.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.models.workflow_models import DetailedPlanStep
from will.orchestration.workflow_orchestrator import WorkflowContext
from will.phases.code_generation_phase import CodeGenerationPhase


def _phase(repo: Path) -> CodeGenerationPhase:
    core_context = MagicMock()
    core_context.git_service.repo_path = str(repo)
    with (
        patch("will.phases.code_generation_phase.DecisionTracer"),
        patch("will.phases.code_generation_phase.PytestSandboxRunner"),
        patch("will.phases.code_generation_phase.WorkDirectoryManager"),
        patch("will.phases.code_generation_phase.ArtifactSaver"),
        patch("will.phases.code_generation_phase.CodeSensor"),
    ):
        phase = CodeGenerationPhase(core_context)
    phase.artifact_saver = MagicMock()
    phase.work_dir_manager = MagicMock()
    phase.work_dir_manager.create_session_directory.return_value = "work/x"
    return phase


def _steps(failed: int, total: int) -> list[DetailedPlanStep]:
    return [
        DetailedPlanStep(
            action="file.edit",
            description=f"step {i}",
            params={"file_path": f"package/m{i}.py"},
            metadata={"generation_failed": True} if i < failed else {},
        )
        for i in range(total)
    ]


@pytest.mark.parametrize(
    ("failed", "total", "ok"), [(2, 5, False), (0, 5, True), (1, 5, True)]
)
async def test_verdict_is_stated_when_generation_falls_short(
    failed: int, total: int, ok: bool, tmp_path: Path
) -> None:
    phase = _phase(tmp_path)
    context = WorkflowContext(goal="g", workflow_type="code_modification", write=False)
    context.results["planning"] = {"execution_plan": [object()] * total}
    with (
        patch("will.phases.code_generation_phase.LimbWorkspace"),
        patch("will.phases.code_generation_phase.ContextService"),
        patch("will.agents.coder_agent.CoderAgent"),
        patch("will.orchestration.prompt_pipeline.PromptPipeline"),
        patch.object(
            phase, "_process_tasks", new=AsyncMock(return_value=_steps(failed, total))
        ),
    ):
        result = await phase.execute(context)
    assert result.ok is ok
    if ok:
        assert result.error == ""
    else:
        assert result.error == (
            f"code generation succeeded for {total - failed}/{total} steps "
            f"(success_rate {(total - failed) / total:.2f} < 0.80)"
        )
    assert result.data["successful_steps"] == total - failed
