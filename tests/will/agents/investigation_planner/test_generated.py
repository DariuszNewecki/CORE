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


from will.agents.investigation_planner import investigation_decisions


# ID: e69c4739-35c7-40c5-882b-384bed41e8ae
def test_investigation_decisions():
    step_one = MagicMock()
    step_one.action = "inspect.layout"
    step_one.step = "Determine repository layout"
    step_one.params = {"root": "/repo"}

    step_two = MagicMock()
    step_two.action = "inspect.artifact_types"
    step_two.step = "Identify artifact types"
    step_two.params = {"kind": "python"}

    records = investigation_decisions([step_one, step_two])

    assert len(records) == 2

    first = records[0]
    assert first["agent"] == "investigation_planner"
    assert first["decision_type"] == "investigation_step_planned"
    assert first["chosen"] == "inspect.layout"
    assert first["rationale"] == "Determine repository layout"
    assert first["params"] == {"root": "/repo"}
    assert first["step_index"] == 1
    assert "inspect.layout" not in first["alternatives"]
    assert first["alternatives"] == sorted(first["alternatives"])

    second = records[1]
    assert second["chosen"] == "inspect.artifact_types"
    assert second["rationale"] == "Identify artifact types"
    assert second["params"] == {"kind": "python"}
    assert second["step_index"] == 2
    assert "inspect.artifact_types" not in second["alternatives"]

    assert investigation_decisions([]) == []



from will.agents.investigation_planner import parse_and_validate_investigation_plan


# ID: 05f6a6a8-07bd-4973-8768-69169cc200c0
def test_parse_and_validate_investigation_plan():
    sentinel_step = object()
    with (
        patch(
            "will.agents.investigation_planner.extract_json_from_response",
            return_value={"plan": [{"action": "read"}]},
        ) as mock_extract,
        patch(
            "will.agents.investigation_planner.plan_steps",
            return_value=[{"action": "read", "target": "x"}],
        ) as mock_plan_steps,
        patch(
            "will.agents.investigation_planner.validate_investigation_plan",
            return_value=[sentinel_step],
        ) as mock_validate,
    ):
        result = parse_and_validate_investigation_plan('{"plan": [{"action": "read"}]}')

    mock_extract.assert_called_once_with('{"plan": [{"action": "read"}]}')
    mock_plan_steps.assert_called_once_with({"plan": [{"action": "read"}]})
    mock_validate.assert_called_once_with([{"action": "read", "target": "x"}])
    assert result == [sentinel_step]
