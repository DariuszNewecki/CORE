from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.autonomy.daily_spend_cap import refuse_when_daily_spend_cap_reached


# ID: 7e4d625b-26a5-45ce-bbdd-397d761b8134
async def test_refuse_when_daily_spend_cap_reached() -> None:
    actions = MagicMock()

    session = MagicMock()
    execute_result = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda self, idx: 0.0 if idx == 0 else 0
    execute_result.one.return_value = row
    session.execute = AsyncMock(return_value=execute_result)

    budget = MagicMock()
    budget.for_task_type.return_value.daily_spend_usd_max = 5.0

    with (
        patch("will.autonomy.daily_spend_cap.is_test_generation", return_value=True),
        patch(
            "will.autonomy.daily_spend_cap.load_generation_budget",
            return_value=budget,
        ),
    ):
        await refuse_when_daily_spend_cap_reached(session, actions)

    session.execute.assert_awaited_once()
    budget.for_task_type.assert_called_once_with("test_generation")
