from __future__ import annotations

from unittest.mock import patch

from mind.logic.engines.cli_gate.checks.async_execution import AsyncExecutionCheck


# ID: bc4b5326-fbad-4fb8-8758-c33c5b09fc3d
def test_AsyncExecutionCheck_verify() -> None:
    # ID: d2077497-50c5-4f21-a445-7463b0eeb7aa
    async def my_async_callback() -> None:
        pass

    commands = [
        {
            "callback": my_async_callback,
            "name": "my_command",
            "file_path": "some/path.py",
        }
    ]

    with patch(
        "cli.utils.decorators.COMMAND_REGISTRY",
        {"my_async_callback": object()},
    ):
        check = AsyncExecutionCheck()
        findings = check.verify(commands, {})

    assert findings == []
