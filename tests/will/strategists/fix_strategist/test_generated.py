from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
# ID: b9d31665-c8f9-4a2a-99ed-017e516dabda
async def test_FixStrategist_execute():
    from will.strategists.fix_strategist import FixStrategist

    strategist = FixStrategist()
    strategist.tracer = MagicMock()

    mock_sequence = [
        {"fix_type": "lint", "priority": 1, "metadata": {"auto_fixable": True}},
        {"fix_type": "format", "priority": 2, "metadata": {"auto_fixable": False}},
    ]

    strategist._select_strategy = MagicMock(return_value="comprehensive")
    strategist._build_sequence = MagicMock(return_value=mock_sequence)
    strategist._determine_execution_mode = MagicMock(return_value="batch")
    strategist._identify_safety_checks = MagicMock(return_value=["backup"])
    strategist._estimate_duration = MagicMock(return_value=12.5)

    result = await strategist.execute(fix_target="all", severity_threshold="low")

    assert result.ok is True
    assert result.data["strategy"] == "comprehensive"
    assert result.data["fix_target"] == "all"
    assert result.data["severity_threshold"] == "low"
    assert result.data["execution_mode"] == "batch"
    assert result.data["safety_checks"] == ["backup"]
    assert result.data["estimated_duration_sec"] == 12.5
    assert len(result.data["fix_sequence"]) == 2
    assert result.next_suggested == "fix_executor"
    strategist.tracer.record.assert_called_once()


from unittest.mock import patch


# ID: b6a2a234-352f-4c84-9f0c-acbcaf253deb
def test_FixStrategist():
    from will.strategists.fix_strategist import FixStrategist

    with patch("will.strategists.fix_strategist.DecisionTracer") as mock_tracer_cls:
        mock_tracer = MagicMock()
        mock_tracer_cls.return_value = mock_tracer

        strategist = FixStrategist()

        assert strategist.tracer is mock_tracer
        mock_tracer_cls.assert_called_once()

    assert "syntax_errors" in FixStrategist.FIX_METADATA
    assert "code_style" in FixStrategist.FIX_METADATA
    assert FixStrategist.FIX_METADATA["syntax_errors"]["priority"] == 1
    assert FixStrategist.FIX_METADATA["code_style"]["priority"] == 4
