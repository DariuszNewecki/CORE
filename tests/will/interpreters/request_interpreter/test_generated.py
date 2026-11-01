from __future__ import annotations

import pytest

from will.interpreters.request_interpreter import RequestInterpreter


@pytest.mark.asyncio
# ID: 245f70d9-a59f-4732-9f35-6706893496ce
async def test_RequestInterpreter_execute():
    interpreter = RequestInterpreter()

    with pytest.raises(NotImplementedError):
        await interpreter.execute("some input", key="value")


from unittest.mock import MagicMock


# ID: c090a11a-af6f-4cc0-8cd6-f7d4eb4e49f4
def test_RequestInterpreter_phase():
    from will.interpreters.request_interpreter import RequestInterpreter

    interpreter = RequestInterpreter.__new__(RequestInterpreter)
    interpreter.something = MagicMock()

    result = interpreter.phase

    assert result is not None
    assert getattr(result, "name", None) == "INTERPRET"


# ID: 9e5d27d3-1d63-41a7-8492-bc453b2d2e82
def test_RequestInterpreter():
    interpreter = RequestInterpreter()

    phase = interpreter.phase
    assert phase is not None

    task = MagicMock()
    task.confidence = 0.87

    result = interpreter._create_result(task, ok=True, metadata={"source": "nl"})

    assert result.component_id == interpreter.component_id
    assert result.ok is True
    assert result.data == {"task": task}
    assert result.phase == phase
    assert result.confidence == 0.87
    assert result.next_suggested == "analyzer"
    assert result.metadata == {"source": "nl"}
    assert result.duration_sec == 0.0



from will.interpreters.request_interpreter import TaskStructure


# ID: 75e34667-2075-494e-9ad6-e5eeda994182
def test_TaskStructure() -> None:
    task_type_cls = TaskStructure.__annotations__["task_type"]
    task_type_value = next(iter(task_type_cls))

    task = TaskStructure(
        task_type=task_type_value,
        intent="Add logging to the handler",
        targets=["handler.py"],
        constraints={"write_mode": "safe", "max_attempts": 3},
        context={"source": "request"},
        confidence=0.9,
    )

    assert task.task_type is task_type_value
    assert task.intent == "Add logging to the handler"
    assert task.targets == ["handler.py"]
    assert task.constraints == {"write_mode": "safe", "max_attempts": 3}
    assert task.context == {"source": "request"}
    assert task.confidence == 0.9
