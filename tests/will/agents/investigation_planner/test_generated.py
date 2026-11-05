from __future__ import annotations

from will.agents.investigation_planner import InvestigationPlanError


# ID: ca9ee43b-44c7-4161-8fa3-da76bb21c2b1
def test_InvestigationPlanError():
    message = "investigation plan is not read-only"
    error = InvestigationPlanError(message)

    assert isinstance(error, Exception)
    assert str(error) == message
    assert error.args == (message,)


from will.agents.investigation_planner import InvestigationStep


# ID: 689c595f-7d81-4d69-b22f-c1ba7ad902a7
def test_InvestigationStep():
    step = InvestigationStep(
        step="gather_logs",
        action="read_file",
        params={"path": "/var/log/app.log", "lines": 100},
    )

    assert step.step == "gather_logs"
    assert step.action == "read_file"
    assert step.params == {"path": "/var/log/app.log", "lines": 100}
    assert isinstance(step.params, dict)


from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.agents.investigation_planner import create_investigation_plan


@pytest.mark.asyncio
# ID: 798d921a-25b6-413f-ba63-c2356c3d01d4
async def test_create_investigation_plan():
    cognitive_service = MagicMock()
    cognitive_service.aget_client_for_role = AsyncMock(return_value=MagicMock())

    model = MagicMock()
    model._artifact = MagicMock()
    model._artifact.manifest.role = "planner"
    model.invoke = AsyncMock(return_value="inspect.layout\ninspect.path")

    expected_steps = [MagicMock(), MagicMock()]

    with (
        patch(
            "will.agents.investigation_planner.PromptModel.load",
            return_value=model,
        ),
        patch(
            "will.agents.investigation_planner.parse_and_validate_investigation_plan",
            return_value=expected_steps,
        ) as mock_parse,
    ):
        result = await create_investigation_plan(
            cognitive_service,
            goal="understand the target",
            reconnaissance_report="target has three directories",
        )

    assert result == expected_steps
    cognitive_service.aget_client_for_role.assert_awaited_once_with("planner")
    model.invoke.assert_awaited_once()
    mock_parse.assert_called_once_with("inspect.layout\ninspect.path")
