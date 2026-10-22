# tests/cli/resources/runtime/test_spend.py

"""`core-admin runtime spend` rendering."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from cli.resources.runtime import spend as spend_module


_SPEND = {
    "days": 7,
    "usd": 0.0012,
    "calls": 14,
    "unpriced": 1,
    "by_day": [{"day": "2026-10-22", "calls": 14, "usd": 0.0012, "unpriced": 1}],
    "by_role_model": [
        {
            "role": "Coder",
            "model": "deepseek-chat",
            "calls": 4,
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "usd": 0.0012,
            "usd_per_call": 0.0003,
            "unpriced": 1,
        }
    ],
}


# ID: 4f9c2e71-8a36-4d5b-9e1f-0c7b3a6d2e58
def test_render_spend_shows_total_and_unpriced() -> None:
    captured = StringIO()
    with patch.object(
        spend_module, "console", Console(file=captured, no_color=True, width=200)
    ):
        spend_module.render_spend(_SPEND)
    out = captured.getvalue()
    assert "2026-10-22" in out
    assert "0.00030" in out
    assert "Last 7 days: USD 0.0012 in 14 calls" in out
    assert "1 calls without a price" in out
