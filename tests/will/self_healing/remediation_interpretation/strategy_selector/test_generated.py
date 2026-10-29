from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.strategy_selector import (
    _CFG,
    StrategySelector,
)


# ID: 88d9f8f3-d63e-4238-a88e-f44900c2b401
def test_StrategySelector_choose_recommended():
    selector = StrategySelector()

    top_strategy = MagicMock()
    top_strategy.score = _CFG.min_recommended_score + 1.0

    other_strategy = MagicMock()
    other_strategy.score = _CFG.min_recommended_score - 1.0

    candidate_strategies = [top_strategy, other_strategy]

    result = selector.choose_recommended(candidate_strategies)

    assert result is top_strategy
