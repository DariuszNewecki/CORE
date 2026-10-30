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
