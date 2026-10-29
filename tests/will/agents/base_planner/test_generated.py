from __future__ import annotations

from unittest.mock import patch

from will.agents.base_planner import parse_and_validate_plan


# ID: f8b39dc7-900a-4426-ac77-8a8bede35247
def test_parse_and_validate_plan():
    response_text = '{"plan": [{"action": "file.write", "step": "write file", "params": {"file_path": "src/a.py"}}]}'

    mock_task = object()
    with (
        patch(
            "will.agents.base_planner.extract_json_from_response",
            return_value={
                "plan": [
                    {
                        "action": "file.write",
                        "step": "write file",
                        "params": {"file_path": "src/a.py"},
                    }
                ]
            },
        ),
        patch(
            "will.agents.base_planner.plan_steps",
            return_value=[
                {
                    "action": "file.write",
                    "step": "write file",
                    "params": {"file_path": "src/a.py"},
                }
            ],
        ),
        patch(
            "will.agents.base_planner.ExecutionTask",
            return_value=mock_task,
        ) as mock_exec_task,
    ):
        result = parse_and_validate_plan(response_text)

    assert result == [mock_task]
    mock_exec_task.assert_called_once_with(
        action="file.write", step="write file", params={"file_path": "src/a.py"}
    )


from will.agents.base_planner import plan_steps


# ID: da7b2194-dc0d-445a-990a-ae02c11c1494
def test_plan_steps():
    steps = ["step one", "step two", "step three"]

    # Bare list is accepted as-is
    assert plan_steps(steps) is steps

    # Object form with "plan" key returns the inner step list
    assert plan_steps({"plan": steps}) is steps

    # Non-plan shapes yield None
    assert plan_steps({"not_plan": steps}) is None
    assert plan_steps({"plan": "not-a-list"}) is None
    assert plan_steps("unexpected") is None
    assert plan_steps(None) is None
