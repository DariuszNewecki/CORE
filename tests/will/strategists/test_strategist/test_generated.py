from __future__ import annotations

from unittest.mock import MagicMock

from will.strategists.test_strategist import TestStrategist


# ID: c01cf015-1527-44d0-8025-7742ea00ae43
async def test_TestStrategist_execute():
    strategist = TestStrategist()
    strategist.tracer = MagicMock()
    strategist.tracer.record = MagicMock()
    strategist._calculate_confidence = MagicMock(return_value=0.9)

    result = await strategist.execute("default")

    assert result.ok is True
    assert result.data["strategy"] == "unit_tests"
    assert result.data["approach"] == "Unit tests with mocked dependencies"
    assert result.next_suggested == "test_generator"
    assert result.confidence == 0.9
    strategist.tracer.record.assert_called_once()
