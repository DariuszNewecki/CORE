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
