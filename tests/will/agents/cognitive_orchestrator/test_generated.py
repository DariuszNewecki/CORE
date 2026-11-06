from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
# ID: 421d23a4-55ba-4226-98ea-3ee56813fa99
async def test_CognitiveOrchestrator_get_client_for_role():
    from will.agents.cognitive_orchestrator import CognitiveOrchestrator as CO

    repo_path = MagicMock()
    mind_state_service = MagicMock()
    provider_factory = MagicMock()

    orchestrator = CO(
        repo_path=repo_path,
        mind_state_service=mind_state_service,
        provider_factory=provider_factory,
    )

    orchestrator._loaded = True
    resource = MagicMock()
    resource.name = "res-1"
    orchestrator._resources = [resource]
    orchestrator._roles = [MagicMock()]
    orchestrator._assignments = [MagicMock()]
    orchestrator._system_operating_mode = "default"

    with (
        patch(
            "will.agents.cognitive_orchestrator.ResourceSelector.select_resources_for_role",
            return_value=[resource],
        ) as mock_select,
        patch(
            "will.agents.cognitive_orchestrator.FallbackAwareLLMClient"
        ) as mock_fallback_cls,
    ):
        mock_wrapper = MagicMock()
        mock_fallback_cls.return_value = mock_wrapper

        result = await orchestrator.get_client_for_role("planner")

        mock_select.assert_called_once()
        mock_fallback_cls.assert_called_once()
        assert result is mock_wrapper


from pathlib import Path
from unittest.mock import AsyncMock

from will.agents.cognitive_orchestrator import CognitiveOrchestrator


# ID: d8b278ee-6435-4c57-865f-10af1134f65d
async def test_CognitiveOrchestrator_initialize():
    repo_path = Path("/tmp/repo")

    mind_state_service = MagicMock()
    mind_state_service.get_llm_resources = AsyncMock(
        return_value=[MagicMock(name="resource1")]
    )
    mind_state_service.get_cognitive_roles = AsyncMock(
        return_value=[MagicMock(name="role1"), MagicMock(name="role2")]
    )
    mind_state_service.get_role_resource_assignments = AsyncMock(
        return_value=[MagicMock(name="assignment1")]
    )
    system_config = MagicMock()
    system_config.operating_mode = "full"
    mind_state_service.get_system_config = AsyncMock(return_value=system_config)

    provider_factory = MagicMock()

    orchestrator = CognitiveOrchestrator(
        repo_path=repo_path,
        mind_state_service=mind_state_service,
        provider_factory=provider_factory,
    )

    await orchestrator.initialize()

    mind_state_service.get_llm_resources.assert_awaited_once()
    mind_state_service.get_cognitive_roles.assert_awaited_once()
    mind_state_service.get_role_resource_assignments.assert_awaited_once()
    mind_state_service.get_system_config.assert_awaited_once()

    assert orchestrator._loaded is True
    assert len(orchestrator._resources) == 1
    assert len(orchestrator._roles) == 2
    assert len(orchestrator._assignments) == 1
    assert orchestrator._system_operating_mode == "full"
