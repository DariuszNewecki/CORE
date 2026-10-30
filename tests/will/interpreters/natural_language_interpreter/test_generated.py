from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from will.interpreters.natural_language_interpreter import NaturalLanguageInterpreter


# ID: 75374b4b-f5c4-4ce7-bd92-8507d713378f
def test_NaturalLanguageInterpreter_execute():
    interpreter = NaturalLanguageInterpreter.__new__(NaturalLanguageInterpreter)

    task_type = MagicMock()
    task_type.value = "implement"
    targets = ["src/foo.py"]
    constraints = {"style": "pep8"}
    expected_result = MagicMock()

    interpreter._classify_intent = MagicMock(return_value=task_type)
    interpreter._extract_targets = MagicMock(return_value=targets)
    interpreter._extract_constraints = MagicMock(return_value=constraints)
    interpreter._calculate_confidence = MagicMock(return_value=0.9)
    interpreter._get_matched_patterns = MagicMock(return_value=["p1"])
    interpreter._create_result = MagicMock(return_value=expected_result)

    fake_task = MagicMock()

    with patch(
        "will.interpreters.natural_language_interpreter.TaskStructure",
        return_value=fake_task,
    ) as mock_task_structure:
        result = asyncio.run(
            NaturalLanguageInterpreter.execute(interpreter, "add a feature to foo.py")
        )

    mock_task_structure.assert_called_once()
    kwargs_used = mock_task_structure.call_args.kwargs
    assert kwargs_used["task_type"] is task_type
    assert kwargs_used["targets"] == targets
    assert kwargs_used["constraints"] == constraints
    assert kwargs_used["intent"] == "add a feature to foo.py"
    assert kwargs_used["confidence"] == 0.9

    interpreter._classify_intent.assert_called_once_with("add a feature to foo.py")
    interpreter._extract_targets.assert_called_once_with("add a feature to foo.py")
    interpreter._extract_constraints.assert_called_once_with("add a feature to foo.py")
    interpreter._create_result.assert_called_once()
    assert result is expected_result
    assert expected_result.duration_sec >= 0.0


import pytest


@pytest.mark.asyncio
# ID: d5d61ecb-c477-4ea7-96a1-44e4efeb58c8
async def test_NaturalLanguageInterpreter():
    interpreter = NaturalLanguageInterpreter()
    result = await interpreter.execute("fix src/models/user.py")

    assert result is not None

    task_type = interpreter._classify_intent("fix src/models/user.py")
    assert task_type is not None
    assert getattr(task_type, "value", str(task_type)).lower() == "fix"

    targets = interpreter._extract_targets("fix src/models/user.py")
    assert "src/models/user.py" in targets

    constraint = interpreter._extract_constraints("dry run fix src/models/user.py")
    assert constraint.get("write") is False
