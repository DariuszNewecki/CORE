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
