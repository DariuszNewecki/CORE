from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from will.strategists.validation_strategist import ValidationStrategist


# ID: 747d1403-0fb5-4ea2-9405-514daf59d4ad
def test_ValidationStrategist_execute():
    strategist = ValidationStrategist.__new__(ValidationStrategist)
    strategist.tracer = MagicMock()

    strategist._classify_risk = MagicMock(return_value="STANDARD")
    strategist._select_strategy = MagicMock(return_value="targeted")
    strategist._map_checks = MagicMock(return_value=["unit_tests", "lint"])
    strategist._determine_threshold = MagicMock(return_value=0.9)
    strategist._determine_enforcement = MagicMock(return_value="advisory")

    result = asyncio.run(
        ValidationStrategist.execute(
            strategist,
            "refactor",
            file_path="src/will/foo.py",
            write_mode=True,
        )
    )

    strategist._classify_risk.assert_called_once_with(
        "src/will/foo.py", "refactor", True
    )
    strategist._select_strategy.assert_called_once_with("STANDARD", "refactor", True)
    strategist._map_checks.assert_called_once_with(
        "targeted", "refactor", "src/will/foo.py"
    )
    strategist._determine_threshold.assert_called_once_with("targeted", "STANDARD")
    strategist._determine_enforcement.assert_called_once_with(
        "targeted", "STANDARD", True
    )
    strategist.tracer.record.assert_called_once()

    assert result.ok is True
    assert result.data["validation_strategy"] == "targeted"
    assert result.data["required_checks"] == ["unit_tests", "lint"]
    assert result.data["quality_threshold"] == 0.9
    assert result.data["enforcement_level"] == "advisory"
    assert result.data["risk_tier"] == "STANDARD"
    assert result.next_suggested == "constitutionalevaluator"
