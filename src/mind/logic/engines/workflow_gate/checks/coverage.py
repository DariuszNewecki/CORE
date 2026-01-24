# src/mind/logic/engines/workflow_gate/checks/coverage.py
# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f

"""
Coverage verification workflow check.
Refactored to be circular-safe.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
class CoverageMinimumCheck(WorkflowCheck):
    """
    Checks if code coverage meets the constitutional threshold.
    """

    check_type = "coverage_minimum"

    def __init__(self, path_resolver: PathResolver) -> None:
        self._paths = path_resolver

    # ID: c360fe9a-1dc3-4f63-9c8a-30ebe3b4f4df
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        threshold = self._load_coverage_threshold()
        current_coverage = params.get("current_coverage")

        if current_coverage is None:
            cov_file = Path("coverage.json")
            if cov_file.exists():
                try:
                    data = json.loads(cov_file.read_text(encoding="utf-8"))
                    current_coverage = data.get("totals", {}).get("percent_covered", 0)
                except Exception as e:
                    logger.warning("Failed to parse coverage.json: %s", e)

        if current_coverage is not None and current_coverage < threshold:
            return [
                f"Coverage too low: {current_coverage:.1f}% (Constitutional Minimum: {threshold}%)"
            ]

        if current_coverage is None:
            return ["No coverage data found. Run 'make test' first."]

        return []

    def _load_coverage_threshold(self) -> float:
        """Load threshold via PathResolver (SSOT)."""
        try:
            # We resolve the path but do not import the registry
            ops_path = self._paths.policy("operations")
            if ops_path.exists():
                data = json.loads(ops_path.read_text(encoding="utf-8"))
                return float(
                    data.get("quality_assurance", {})
                    .get("coverage_requirements", {})
                    .get("minimum_threshold", 75)
                )
        except Exception:
            pass
        return 75.0
