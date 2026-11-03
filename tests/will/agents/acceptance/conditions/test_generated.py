from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.agents.acceptance.conditions import CompositeAcceptanceCondition


# ID: 64769bd5-76d4-43ad-bb68-cc6d7c9fbfd2
async def test_CompositeAcceptanceCondition_evaluate():
    accepted_result = MagicMock()
    accepted_result.accepted = True
    accepted_result.violation_summary = ""

    condition_a = MagicMock()
    condition_a.evaluate = AsyncMock(return_value=accepted_result)
    condition_b = MagicMock()
    condition_b.evaluate = AsyncMock(return_value=accepted_result)

    composite = CompositeAcceptanceCondition([condition_a, condition_b])

    result = await composite.evaluate("some code")

    assert result.accepted is True
    assert result.violation_summary == ""
    condition_a.evaluate.assert_awaited_once_with("some code")
    condition_b.evaluate.assert_awaited_once_with("some code")


import asyncio


# ID: 18835eea-3ae1-404d-91fa-6a8e21f9f756
def test_CompositeAcceptanceCondition():
    passing = MagicMock()
    passing.evaluate = AsyncMock(
        return_value=MagicMock(accepted=True, violation_summary="")
    )
    failing = MagicMock()
    failing.evaluate = AsyncMock(
        return_value=MagicMock(accepted=False, violation_summary="boom")
    )

    # ID: 61206fcf-411d-421f-948d-8fcbf16bb199
    async def run():
        composite = CompositeAcceptanceCondition([passing, failing])
        result = await composite.evaluate("ok()[code]")
        return composite, result

    composite, result = asyncio.run(run())

    assert result.accepted is False
    assert result.violation_summary == "boom"
    passing.evaluate.assert_awaited_once_with("ok()[code]")
    failing.evaluate.assert_awaited_once_with("ok()[code]")
    assert composite._conditions == [passing, failing]
