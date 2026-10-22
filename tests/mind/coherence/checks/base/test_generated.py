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


import asyncio


# ID: e994f248-1cd3-4836-9504-e0a7dd4f722c
def test_CheckClass():
    from mind.coherence.checks.base import CheckClass

    class _DummyCheck:
        relation = "test_relation"

        # ID: fd19de08-e07d-4c65-a5e8-5ac28e508811
        async def run(self):
            return []

    assert isinstance(_DummyCheck.relation, str)
    assert hasattr(_DummyCheck, "run")

    instance = _DummyCheck()
    instance.run = AsyncMock(return_value=[])
    result = asyncio.run(instance.run())
    assert result == []
    instance.run.assert_awaited_once()

    assert isinstance(CheckClass, type)
    assert hasattr(CheckClass, "run")


from mind.coherence.checks.base import CheckIncomplete


# ID: 83b83fcd-5438-4ab5-a604-a8205d7514be
def test_CheckIncomplete():
    candidates = [object(), object()]
    exc = CheckIncomplete(
        candidates=candidates,
        judged=3,
        unjudged=2,
        first_error="judge unreachable",
    )

    assert exc.candidates is candidates
    assert exc.judged == 3
    assert exc.unjudged == 2
    assert str(exc) == "2 of 5 pairs unjudged: judge unreachable"
    assert isinstance(exc, Exception)
