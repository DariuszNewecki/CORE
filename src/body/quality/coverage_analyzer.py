# src/body/quality/coverage_analyzer.py

"""
Analyzes codebase coverage and module structure.

Provides coverage measurement and module complexity analysis
to support intelligent test prioritization.
"""

from __future__ import annotations

from pathlib import Path

# REFACTORED: Removed direct settings import
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG = load_operational_config().coverage


# ID: 2b075104-ab91-4ea3-931b-a9be87d56799
class CoverageAnalyzer:
    """
    Analyzes test coverage and module structure for prioritization.
    """

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    # ID: 168e0d67-a382-48a5-9dd5-79eeb9656cfa
    async def get_module_coverage(self) -> dict[str, float]:
        """
        Gets current coverage percentage for each module.

        The suite runs in the sandbox runner with coverage measured there
        (ADR-132 D10.10); the per-file numbers come back in the result.
        Integration tests the service excludes do not count, so numbers can
        read lower than a full local run.

        Returns:
            Dict mapping repo-relative file paths to coverage percentages;
            empty when the sandbox produced no coverage.
        """
        from body.sandbox.repo_tests import run_in_sandbox

        try:
            result = await run_in_sandbox(
                self.repo_path,
                ["tests"],
                timeout_sec=int(_CFG.collect_timeout_sec),
                coverage=True,
            )
        except Exception as e:
            logger.debug("Could not get module coverage: %s", e)
            return {}
        files = result.coverage.get("files")
        if not files:
            logger.debug(
                "No coverage from the sandbox (%s: %s %s)",
                result.status,
                result.reason,
                result.coverage.get("error", ""),
            )
            return {}
        return {str(path): float(pct) for path, pct in files.items()}
