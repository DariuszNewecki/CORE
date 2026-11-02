from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.agents.planner_agent import PlannerAgent


@pytest.mark.asyncio
# ID: a7855cd5-1ff0-412e-aa58-618d42149936
async def test_PlannerAgent_create_execution_plan():
    # Arrange
    cognitive_service = MagicMock()
    cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())
    repo_path = Path("/tmp/repo")

    with (
        patch("will.agents.planner_agent.PolicyVectorizer", MagicMock()),
        patch("will.agents.planner_agent.PromptModel") as prompt_model_cls,
        patch("will.agents.planner_agent.DecisionTracer") as tracer_cls,
    ):
        plan_goal_model = MagicMock()
        plan_goal_model._artifact.manifest.role = "planner"
        plan_goal_model.invoke = AsyncMock(return_value="valid plan response")
        prompt_model_cls.load.return_value = plan_goal_model

        tracer_instance = MagicMock()
        tracer_cls.return_value = tracer_instance

        agent = PlannerAgent(
            cognitive_service=cognitive_service,
            repo_path=repo_path,
            qdrant_service=None,
        )
        # Ensure tracer used in method is the mock
        agent.tracer = tracer_instance

        expected_plan = [MagicMock(), MagicMock()]

        agent._fetch_constitutional_context = AsyncMock(return_value="CONST RULES")
        agent._load_qa_constraints = MagicMock(return_value="QA CONSTRAINTS")

        action = MagicMock()
        action.action_id = "act1"
        action.description = "Do something"
        action.impact_level = "low"

        fake_prompt_dir = MagicMock(spec=Path)
        (fake_prompt_dir / "system.txt")  # sanity, no-op

        path_resolver_instance = MagicMock()
        prompt_path = MagicMock(spec=Path)
        system_txt = MagicMock(spec=Path)
        system_txt.read_text.return_value = "SYSTEM PROMPT TEMPLATE"
        prompt_path.__truediv__ = MagicMock(return_value=system_txt)
        path_resolver_instance.prompt.return_value = prompt_path

        with (
            patch(
                "will.agents.planner_agent.PathResolver",
                return_value=path_resolver_instance,
            ),
            patch("will.agents.planner_agent.action_registry") as action_registry,
            patch(
                "will.agents.planner_agent.build_planning_prompt",
                return_value="BUILT PROMPT",
            ) as build_prompt,
            patch(
                "will.agents.planner_agent.parse_and_validate_plan",
                return_value=expected_plan,
            ) as parse_plan,
        ):
            action_registry.list_all.return_value = [action]

            # Act
            result = await agent.create_execution_plan("build a thing", "recon report")

    # Assert
    assert result == expected_plan
    agent._fetch_constitutional_context.assert_awaited_once_with("build a thing")
    agent._load_qa_constraints.assert_called_once()
    action_registry.list_all.assert_called_once()
    build_prompt.assert_called_once()
    prompt_model_cls.load.assert_called_once_with("plan_goal")
    plan_goal_model.invoke.assert_awaited_once()
    parse_plan.assert_called_once_with("valid plan response")
    tracer_instance.record.assert_called_once()
    cognitive_service.aget_client_for_role.assert_awaited_once_with("planner")





# ID: 00adb47a-5cca-4038-9b97-ab5447f02c10
def test_PlannerAgent():
    cognitive_service = MagicMock()
    repo_path = Path("/tmp/repo")

    with (
        patch("will.agents.planner_agent.PromptModel") as mock_prompt_model,
        patch("will.agents.planner_agent.PolicyVectorizer") as mock_policy_vectorizer,
        patch("will.agents.planner_agent.DecisionTracer") as mock_tracer,
    ):
        mock_prompt_model.load.return_value = MagicMock()
        mock_tracer.return_value = MagicMock()

        agent = PlannerAgent(
            cognitive_service=cognitive_service,
            repo_path=repo_path,
            qdrant_service=None,
            max_retries=3,
        )

        assert agent.cognitive_service is cognitive_service
        assert agent.repo_path == repo_path
        assert agent.max_retries == 3
        assert agent.policy_vectorizer is None
        mock_prompt_model.load.assert_called_once_with("plan_goal")
        mock_policy_vectorizer.assert_not_called()
