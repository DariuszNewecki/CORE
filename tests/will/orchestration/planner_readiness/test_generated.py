from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.orchestration.planner_readiness import probe_planner_readiness


@pytest.mark.asyncio
# ID: 1b9850fb-c99f-4612-9bac-b38666494f46
async def test_probe_planner_readiness():
    model = MagicMock()
    model._artifact.manifest.role = "planner"
    cognitive = MagicMock()
    cognitive.aget_client_for_role = AsyncMock(return_value=MagicMock())
    context = MagicMock()
    context.cognitive_service = cognitive

    with patch(
        "shared.ai.prompt_model.PromptModel.load",
        return_value=model,
    ) as mock_load:
        result = await probe_planner_readiness(context)

    assert result is None
    mock_load.assert_called_once_with("plan_goal")
    cognitive.aget_client_for_role.assert_awaited_once_with("planner")


import asyncio
from types import SimpleNamespace

from will.orchestration.planner_readiness import resolve_brain_services


# ID: b05ab7bd-4e08-449a-add9-ea18b3be6c0b
def test_resolve_brain_services() -> None:
    cognitive_service = object()
    auditor_context = object()

    registry = MagicMock()
    registry.get_cognitive_service = AsyncMock(return_value=cognitive_service)
    registry.get_auditor_context = AsyncMock(return_value=auditor_context)

    context = SimpleNamespace(
        cognitive_service=None,
        auditor_context=None,
        registry=registry,
    )

    asyncio.run(resolve_brain_services(context))

    registry.get_cognitive_service.assert_awaited_once()
    registry.get_auditor_context.assert_awaited_once()
    assert context.cognitive_service is cognitive_service
    assert context.auditor_context is auditor_context
