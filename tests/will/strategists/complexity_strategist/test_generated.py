from __future__ import annotations

from unittest.mock import patch

import pytest

from will.strategists.complexity_strategist import ComplexityStrategist


@pytest.mark.asyncio
# ID: 6c5d5cd3-432e-484d-98b0-9a5b1e7c8972
async def test_ComplexityStrategist() -> None:
    strategist = ComplexityStrategist.__new__(ComplexityStrategist)

    with (
        patch.object(
            ComplexityStrategist,
            "component_id",
            new_callable=lambda: property(lambda self: "comp-123"),
        ),
        patch.object(
            ComplexityStrategist,
            "phase",
            new_callable=lambda: property(lambda self: "analysis"),
        ),
    ):
        result = await ComplexityStrategist.execute(
            strategist, complexity_score=5, extra="ignored"
        )

    assert result.ok is True
    assert result.component_id == "comp-123"
    assert result.phase == "analysis"
    assert result.data["strategy"] == "logic_simplification"
    assert result.data["target_reduction"] == 0.3
    assert result.duration_sec >= 0
