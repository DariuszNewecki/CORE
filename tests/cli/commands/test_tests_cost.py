# tests/cli/commands/test_tests_cost.py
"""`core-admin tests cost`: per role/model totals and USD per call (DB mocked)."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console


# ID: 6a1e9d3f-2b74-4c58-9e0a-71f4c2d8b6e5
@pytest.mark.asyncio
async def test_tests_cost_prints_totals_and_per_call() -> None:
    rows = MagicMock()
    rows.fetchall.return_value = [
        ("Coder", "deepseek-chat", 4, 1000, 200, Decimal("0.0012"), 0),
        ("Vectorizer", "nomic-embed-text-8k", 10, 50, 0, Decimal("0"), 0),
    ]
    attempts = MagicMock()
    attempts.scalar_one.return_value = 3

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[rows, attempts])
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    captured = StringIO()
    from cli.commands.tests import tests_cost

    with (
        patch("cli.commands.tests.get_session", return_value=session),
        patch(
            "cli.commands.tests.console",
            Console(file=captured, no_color=True, width=200),
        ),
    ):
        await tests_cost.__wrapped__(MagicMock(), days=7)

    out = captured.getvalue()
    assert "0.00030" in out  # 0.0012 USD / 4 calls
    assert "Last 7 days: USD 0.0012 in 14 calls; 3 test-generation attempts" in out
