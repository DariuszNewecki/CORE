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
