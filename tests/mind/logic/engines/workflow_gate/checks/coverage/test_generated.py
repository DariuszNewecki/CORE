from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.logic.engines.workflow_gate.checks.coverage import CoverageMinimumCheck


# ID: 2fb6de7e-7864-4cd6-b41e-c58fe387faac
async def test_coverage_minimum_check_verify() -> None:
    path_resolver = MagicMock()
    check = CoverageMinimumCheck(path_resolver)

    with patch.object(
        CoverageMinimumCheck, "_load_coverage_threshold", return_value=80
    ):
        result = await check.verify(None, {"current_coverage": 95.0})

    assert result == []
