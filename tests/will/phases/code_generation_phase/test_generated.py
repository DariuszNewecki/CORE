from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.phases.code_generation_phase import CodeGenerationPhase


@pytest.mark.asyncio
# ID: c99c56cb-3332-4587-b6e7-210b21dc1f5e
async def test_CodeGenerationPhase_execute():
    with (
        patch("will.phases.code_generation_phase.DecisionTracer"),
        patch("will.phases.code_generation_phase.PytestSandboxRunner"),
        patch("will.phases.code_generation_phase.WorkDirectoryManager"),
        patch("will.phases.code_generation_phase.ArtifactSaver"),
        patch("will.phases.code_generation_phase.CodeSensor"),
        patch("will.phases.code_generation_phase.FilePathExtractor"),
        patch("will.phases.code_generation_phase.DeterministicSplitPlanner"),
    ):
        core_context = MagicMock()
        core_context.path_resolver = MagicMock()
        core_context.file_service = MagicMock()
        core_context.git_service.repo_path = "/tmp/repo"
        core_context.cognitive_service = MagicMock()
        core_context.action_executor = MagicMock()
        core_context.auditor_context = MagicMock()
        core_context.context_service = MagicMock()
        core_context.qdrant_service = MagicMock()

        phase = CodeGenerationPhase(core_context)

        step = MagicMock()
        step.metadata = {}

        phase._process_tasks = AsyncMock(return_value=[step])
        phase.work_dir_manager.create_session_directory = MagicMock(
            return_value="work/session"
        )
        phase.artifact_saver.save_generation_artifacts = MagicMock()

        context = MagicMock()
        context.workflow_type = "develop"
        context.goal = "do the thing"
        context.results = {"planning": {"execution_plan": [{"step": "one"}]}}

        with (
            patch("will.phases.code_generation_phase.LimbWorkspace") as mock_workspace,
            patch("will.phases.code_generation_phase.ContextService") as mock_ctx_svc,
            patch(
                "will.phases.code_generation_phase._serialize_detailed_plan",
                return_value={"serialized": True},
            ),
            patch("will.agents.coder_agent.CoderAgent") as mock_coder,
            patch("will.orchestration.prompt_pipeline.PromptPipeline") as mock_pipeline,
        ):
            mock_workspace.return_value = MagicMock()
            mock_ctx_svc.return_value = MagicMock()
            mock_coder.return_value = MagicMock()
            mock_pipeline.return_value = MagicMock()

            result = await phase.execute(context)

    assert result.ok is True
    assert result.name == "code_generation"
    assert result.data["success_rate"] == 1.0
    assert result.data["total_steps"] == 1
    assert result.data["successful_steps"] == 1
    assert result.data["work_directory"] == "work/session"
    phase._process_tasks.assert_awaited_once()
    phase.artifact_saver.save_generation_artifacts.assert_called_once()


from pathlib import Path


# ID: b09f0907-5abf-41b0-bdfe-338c7cc71143
def test_CodeGenerationPhase():
    core_context = MagicMock()
    core_context.path_resolver = MagicMock()
    core_context.file_service = MagicMock()
    core_context.git_service = MagicMock()
    core_context.git_service.repo_path = Path("/tmp/repo")

    with (
        patch("will.phases.code_generation_phase.DecisionTracer") as mock_tracer,
        patch("will.phases.code_generation_phase.PytestSandboxRunner") as mock_runner,
        patch("will.phases.code_generation_phase.WorkDirectoryManager") as mock_wdm,
        patch("will.phases.code_generation_phase.ArtifactSaver") as mock_saver,
        patch("will.phases.code_generation_phase.CodeSensor") as mock_code_sensor,
        patch("will.phases.code_generation_phase.FilePathExtractor") as mock_extractor,
        patch(
            "will.phases.code_generation_phase.DeterministicSplitPlanner"
        ) as mock_split_planner,
    ):
        phase = CodeGenerationPhase(core_context)

    assert phase.context is core_context
    assert phase.tracer is mock_tracer.return_value
    assert phase.file_service is core_context.file_service
    assert phase.execution_sensor is mock_runner.return_value
    assert phase.work_dir_manager is mock_wdm.return_value
    assert phase.artifact_saver is mock_saver.return_value
    assert phase.code_sensor is mock_code_sensor.return_value
    assert phase.path_extractor is mock_extractor.return_value
    assert phase.split_planner is mock_split_planner.return_value

    mock_tracer.assert_called_once_with(
        path_resolver=core_context.path_resolver,
        agent_name="CodeGenerationPhase",
    )
    mock_runner.assert_called_once_with(
        file_handler=core_context.file_service,
        repo_root=str(core_context.git_service.repo_path),
    )
    mock_wdm.assert_called_once_with(core_context.file_service)
    mock_saver.assert_called_once_with(core_context.file_service)
    mock_code_sensor.assert_called_once_with(mock_runner.return_value)
    mock_split_planner.assert_called_once_with(core_context)
