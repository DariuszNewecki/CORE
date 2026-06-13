"""Unit tests for LLM cost-estimate computation — #620.

Covers the pure `_compute_cost_estimate` helper that prices an exchange
from token counts and per-million-token rates. The DB-backed rate lookup
(`_lookup_model_rate`) and the writer wiring are exercised against the live
schema, not here; these tests pin the arithmetic and its edge cases.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from shared.infrastructure.llm.client import _compute_cost_estimate


def test_deepseek_chat_rate() -> None:
    # 1,000,000 in + 1,000,000 out at 0.14 / 0.28 => 0.14 + 0.28 = 0.42
    cost = _compute_cost_estimate(
        1_000_000, 1_000_000, Decimal("0.140000"), Decimal("0.280000")
    )
    assert cost == Decimal("0.420000")


def test_sonnet_rate() -> None:
    # 10,000 in @ $3/Mtok + 2,000 out @ $15/Mtok = 0.03 + 0.03 = 0.06
    cost = _compute_cost_estimate(
        10_000, 2_000, Decimal("3.000000"), Decimal("15.000000")
    )
    assert cost == Decimal("0.060000")


def test_zero_rate_local_model_is_zero() -> None:
    cost = _compute_cost_estimate(
        50_000, 10_000, Decimal("0.000000"), Decimal("0.000000")
    )
    assert cost == Decimal("0.000000")


def test_none_token_counts_treated_as_zero() -> None:
    assert _compute_cost_estimate(
        None, None, Decimal("3.000000"), Decimal("15.000000")
    ) == Decimal("0.000000")
    # Only completion tokens recorded.
    assert _compute_cost_estimate(
        None, 1_000_000, Decimal("0.140000"), Decimal("0.280000")
    ) == Decimal("0.280000")


def test_result_quantized_to_six_places() -> None:
    # A single token at a tiny rate rounds to the column's 6dp precision.
    cost = _compute_cost_estimate(1, 0, Decimal("0.140000"), Decimal("0.280000"))
    # 1 * 0.14 / 1e6 = 0.00000014 -> rounds half-up to 0.000000
    assert cost == Decimal("0.000000")
    assert cost.as_tuple().exponent == -6


def test_rounding_is_half_up() -> None:
    # 5 tokens * 1.0 / 1e6 = 0.000005 exactly — no rounding needed.
    assert _compute_cost_estimate(
        5, 0, Decimal("1.000000"), Decimal("0.000000")
    ) == Decimal("0.000005")
    # 1 token * 1.5 / 1e6 = 0.0000015 -> half-up -> 0.000002
    assert _compute_cost_estimate(
        1, 0, Decimal("1.500000"), Decimal("0.000000")
    ) == Decimal("0.000002")


def test_realistic_deepseek_exchange() -> None:
    # 8,500 prompt + 1,200 completion at deepseek rates.
    cost = _compute_cost_estimate(
        8_500, 1_200, Decimal("0.140000"), Decimal("0.280000")
    )
    # (8500*0.14 + 1200*0.28) / 1e6 = (1190 + 336)/1e6 = 0.001526
    assert cost == Decimal("0.001526")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
