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
