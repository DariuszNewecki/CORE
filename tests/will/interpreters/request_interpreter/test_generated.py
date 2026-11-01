from __future__ import annotations

import pytest

from will.interpreters.request_interpreter import RequestInterpreter


@pytest.mark.asyncio
# ID: 245f70d9-a59f-4732-9f35-6706893496ce
async def test_RequestInterpreter_execute():
    interpreter = RequestInterpreter()

    with pytest.raises(NotImplementedError):
        await interpreter.execute("some input", key="value")
