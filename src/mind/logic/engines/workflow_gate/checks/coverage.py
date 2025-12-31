# src/mind/logic/engines/workflow_gate/checks/coverage.py

"""
Coverage verification workflow check.

Verifies that code coverage meets constitutional threshold.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
class CoverageMinimumCheck(WorkflowCheck):
    """
    Checks if code coverage meets the constitutional threshold.

    Reads coverage.json or accepts current_coverage from params.
    """

    check_type = "coverage_minimum"

    # ID: 0dcd0e36-61d4-4cb7-a048-3b14b5c8cedf
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify coverage meets threshold.

        Args:
            file_path: Unused (context-level check)
            params: May include 'current_coverage' override

        Returns:
            List of violations if coverage is too low or unavailable
        """
        threshold = self._load_coverage_threshold()
        current_coverage = params.get("current_coverage")

        if current_coverage is None:
            cov_file = Path("coverage.json")
            if cov_file.exists():
                try:
                    data = json.loads(cov_file.read_text())
                    current_coverage = data.get("totals", {}).get("percent_covered", 0)
                except (json.JSONDecodeError, KeyError, Exception) as e:
                    logger.warning("Failed to parse coverage.json: %s", e)

        if current_coverage is not None and current_coverage < threshold:
            return [
                f"Coverage too low: {current_coverage:.1f}% (Constitutional Minimum: {threshold}%)"
            ]

        if current_coverage is None:
            return [
                "No coverage data found. Coverage must be measured before integration."
            ]

        return []

    def _load_coverage_threshold(self) -> float:
        """Load coverage threshold from constitutional operations policy."""
        try:
            ops_policy = settings.paths.governance("operations.json")
            if ops_policy.exists():
                data = json.loads(ops_policy.read_text())
                return float(
                    data.get("rules", {})
                    .get("testing", {})
                    .get("min_coverage_percent", 75)
                )
        except Exception as e:
            logger.warning("Could not load coverage threshold from policy: %s", e)

        return 75.0  # Constitutional default
