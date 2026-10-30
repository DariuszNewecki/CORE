from __future__ import annotations

from unittest.mock import MagicMock

from will.autonomy.plan_to_proposal import convert_execution_plan


# ID: 6daa972f-75a3-475d-ade9-21efe928fc32
def test_convert_execution_plan():
    task_a = MagicMock()
    task_a.action = "modify_file"
    task_a.step = "step_1"
    task_a.params.file_path = "src/alpha.py"
    task_a.params.model_dump.return_value = {"file_path": "src/alpha.py"}

    task_b = MagicMock()
    task_b.action = "create_file"
    task_b.step = "step_2"
    task_b.params.file_path = "src/beta.py"
    task_b.params.model_dump.return_value = {"file_path": "src/beta.py"}

    scope, actions = convert_execution_plan(
        [task_a, task_b], workflow_type="code_modification"
    )

    assert scope.files == ["src/alpha.py", "src/beta.py"]
    assert len(actions) == 2
    assert actions[0].action_id == "modify_file"
    assert actions[0].order == 0
    assert actions[0].parameters == {"file_path": "src/alpha.py"}
    assert actions[1].action_id == "create_file"
    assert actions[1].order == 1
    assert actions[1].parameters == {"file_path": "src/beta.py"}
