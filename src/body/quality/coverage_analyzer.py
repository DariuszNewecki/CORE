# src/body/quality/coverage_analyzer.py

"""
Analyzes codebase coverage and module structure.

Provides coverage measurement and module complexity analysis
to support intelligent test prioritization.
"""

from __future__ import annotations

import json
from pathlib import Path

# REFACTORED: Removed direct settings import
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.utils.subprocess_utils import run_command


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
    def get_module_coverage(self) -> dict[str, float]:
        """
        Gets current coverage percentage for each module.

        Returns:
            Dict mapping file paths to coverage percentages
        """
        try:
            run_command(
                ["poetry", "run", "pytest", "--cov=src", "--cov-report=json", "-q"],
                cwd=self.repo_path,
                timeout=_CFG.collect_timeout_sec,
            )
            coverage_json = self.repo_path / "coverage.json"
            if coverage_json.exists():
                data = json.loads(coverage_json.read_text())
                module_coverage = {}
                for file_path, file_data in data.get("files", {}).items():
                    summary = file_data.get("summary", {})
                    percent = summary.get("percent_covered", 0)
                    module_coverage[file_path] = round(percent, 2)
                return module_coverage
        except Exception as e:
            logger.debug("Could not get module coverage: %s", e)
        return {}
