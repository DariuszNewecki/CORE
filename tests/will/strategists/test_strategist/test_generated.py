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


from unittest.mock import patch

import pytest


@pytest.mark.asyncio
# ID: 0575208d-8633-4a59-92e4-2420daeb2383
async def test_TestStrategist():
    with patch("will.strategists.test_strategist.DecisionTracer") as mock_tracer_cls:
        mock_tracer = MagicMock()
        mock_tracer_cls.return_value = mock_tracer

        strategist = TestStrategist()

        result = await strategist.execute(
            file_type="sqlalchemy_model",
            complexity="medium",
        )

    assert result.ok is True
    assert result.data["strategy"] == "integration_tests"
    assert result.data["approach"] == "Integration tests with database fixtures"
    assert (
        "Do NOT use isinstance() on SQLAlchemy type annotations"
        in result.data["constraints"]
    )
    assert result.data["strategy"] == "integration_tests"
    assert result.next_suggested == "test_generator"
    assert 0.0 <= result.confidence <= 1.0

    mock_tracer.record.assert_called_once()
    record_kwargs = mock_tracer.record.call_args.kwargs
    assert record_kwargs["agent"] == "TestStrategist"
    assert record_kwargs["chosen_action"] == "integration_tests"
