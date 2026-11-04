from __future__ import annotations

from will.strategists.clarity_strategist import ClarityStrategist


# ID: 8f47b9d3-8605-4654-b877-d40818ee8aaf
def test_ClarityStrategist_execute():
    import asyncio

    strategist = ClarityStrategist.__new__(ClarityStrategist)
    type(strategist).component_id = property(lambda self: "clarity_component")
    type(strategist).phase = "clarity"

    result = asyncio.run(
        ClarityStrategist.execute(strategist, complexity_score=1, line_count=10)
    )

    assert result.ok is True
    assert result.component_id == "clarity_component"
    assert result.phase == "clarity"
    assert result.data["strategy"] == "readability_polish"
    assert result.data["target_complexity_reduction"] == 0.2


import asyncio
from unittest.mock import MagicMock, patch


# ID: 915c1ef8-f5ae-45e6-a3cd-02bf77fad180
def test_ClarityStrategist():
    from will.strategists.clarity_strategist import ClarityStrategist

    strategist = MagicMock(spec=ClarityStrategist)
    strategist.component_id = "clarity-component"
    strategist.phase = "analysis"

    cfg = MagicMock()
    cfg.structural_complexity = 10
    cfg.structural_lines = 300
    cfg.logic_simplification_threshold = 5

    with (
        patch("will.strategists.clarity_strategist._CFG_CL", cfg),
        patch("will.strategists.clarity_strategist.time") as mock_time,
    ):
        mock_time.time.side_effect = [100.0, 100.5]

        result = asyncio.run(
            ClarityStrategist.execute(strategist, complexity_score=3, line_count=50)
        )

    assert result.ok is True
    assert result.component_id == "clarity-component"
    assert result.phase == "analysis"
    assert result.data["strategy"] == "readability_polish"
    assert "instruction" in result.data
    assert result.data["target_complexity_reduction"] == 0.2
