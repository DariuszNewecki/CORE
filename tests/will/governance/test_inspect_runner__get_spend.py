# tests/will/governance/test_inspect_runner__get_spend.py

"""get_spend (ADR-172): totals, per day and per role/model; unpriced counted."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from will.governance.inspect_runner import get_spend


def _result(rows: list[tuple]) -> MagicMock:
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


# ID: 3e7a1c58-2d94-4b6f-8a0e-5f1c9d2b7e63
async def test_spend_totals_per_call_and_unpriced() -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(
                [
                    ("Coder", "deepseek-chat", 4, 1000, 200, Decimal("0.0012"), 1),
                    ("Vectorizer", "nomic-embed-text-8k", 10, 50, 0, Decimal("0"), 0),
                ]
            ),
            _result([(date(2026, 10, 22), 14, Decimal("0.0012"), 1)]),
        ]
    )

    spend = await get_spend(session, days=7)

    assert spend["days"] == 7
    assert spend["calls"] == 14
    assert spend["unpriced"] == 1
    assert abs(spend["usd"] - 0.0012) < 1e-9
    assert spend["by_role_model"][0]["usd_per_call"] == 0.0003
    assert spend["by_day"] == [
        {"day": "2026-10-22", "calls": 14, "usd": 0.0012, "unpriced": 1}
    ]
    for call in session.execute.await_args_list:
        assert call.args[1] == {"days": 7}
