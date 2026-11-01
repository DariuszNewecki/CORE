from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from will.interpreters.cli_args_interpreter import CLIArgsInterpreter


@pytest.mark.asyncio
# ID: 605bf201-4d35-4a4d-b050-64de6ed87783
async def test_CLIArgsInterpreter_execute():
    interpreter = CLIArgsInterpreter()

    fake_result = MagicMock()
    fake_result.duration_sec = 0.0
    interpreter._create_result = MagicMock(return_value=fake_result)

    result = await CLIArgsInterpreter.execute(
        interpreter,
        command="fix",
        subcommand="clarity",
        targets=["src/foo.py"],
        write=True,
    )

    interpreter._create_result.assert_called_once()
    call_args, call_kwargs = interpreter._create_result.call_args
    task = call_args[0] if call_args else call_kwargs.get("task")

    assert task.intent == "fix clarity src/foo.py"
    assert task.targets == ["src/foo.py"]
    assert task.constraints == {"write": True}
    assert task.confidence == 1.0
    assert task.context == {
        "source": "cli_args",
        "command": "fix",
        "subcommand": "clarity",
    }
    assert call_kwargs["metadata"] == {
        "command": "fix",
        "subcommand": "clarity",
        "flags": {"write": True},
    }
    assert result is fake_result
