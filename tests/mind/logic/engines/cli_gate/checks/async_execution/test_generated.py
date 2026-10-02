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





# ID: 165b432c-4f2f-40f5-971e-6a32998066e2
def test_AsyncExecutionCheck():
    check = AsyncExecutionCheck()

    # ID: 136b6637-7fe7-4061-9937-48e9dcf2ede9
    async def decorated_cb():
        return None

    decorated_cb.__name__ = "decorated_cb"

    # ID: 7236f1f4-bc9d-4577-b57d-e32fdd033728
    async def undecorated_cb():
        return None

    undecorated_cb.__name__ = "undecorated_cb"

    commands = [
        {"callback": decorated_cb, "name": "decorated", "file_path": "a.py"},
        {"callback": undecorated_cb, "name": "undecorated", "file_path": "b.py"},
    ]

    with patch(
        "cli.utils.decorators.COMMAND_REGISTRY",
        {"decorated_cb": decorated_cb},
    ):
        findings = check.verify(commands, {})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == "cli_gate.async_execution"
    assert "undecorated" in finding.message
    assert finding.context["command_name"] == "undecorated"
    assert finding.context["required_decorator"] == "core_command"
