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
