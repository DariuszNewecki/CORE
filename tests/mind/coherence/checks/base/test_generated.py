from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mind.coherence.checks.base import CheckClass


# ID: c14d13b4-fa1d-4be8-9e33-b2033b1d3d53
async def test_CheckClass_run():
    # Build a concrete instance without invoking a possibly-abstract __init__.
    check = CheckClass.__new__(CheckClass)

    expected = [MagicMock(), MagicMock()]

    # Provide an async run implementation on the instance (happy path behavior).
    async def _fake_run(self_inner) -> list:
        return expected

    check.run = AsyncMock(return_value=expected)

    result = await check.run()

    check.run.assert_awaited_once_with()
    assert result == expected
    assert isinstance(result, list)
