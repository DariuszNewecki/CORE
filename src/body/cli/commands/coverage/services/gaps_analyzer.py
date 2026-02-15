# src/body/cli/commands/coverage/services/gaps_analyzer.py
"""Service for analyzing coverage gaps and identifying low-coverage modules."""

from __future__ import annotations

from typing import Any

from body.self_healing.coverage_analyzer import CoverageAnalyzer
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class GapsAnalyzer:
    """Analyzes coverage data to identify gaps and priorities."""

    def __init__(self):
        self.analyzer = CoverageAnalyzer()

    # ID: c902f595-d5bb-491e-94ea-cff937370d27
    def get_coverage_map(self) -> dict[str, float]:
        """Get coverage percentage for all modules."""
        return self.analyzer.get_module_coverage()

    # ID: 9ac607c3-502e-4cd1-9349-26fe7044d996
    def find_gaps(self, threshold: float = 75.0) -> dict[str, Any]:
        """
        Find modules below coverage threshold.

        Args:
            threshold: Coverage percentage threshold (0-100)

        Returns:
            dict with keys:
                - below_threshold: list of (module, coverage) tuples
                - sorted_lowest: list of lowest 20 modules
                - stats: summary statistics
        """
        coverage_map = self.get_coverage_map()

        if not coverage_map:
            return {
                "below_threshold": [],
                "sorted_lowest": [],
                "stats": {"total": 0, "below_threshold": 0, "below_50": 0},
            }

        # Sort by coverage (lowest first)
        sorted_modules = sorted(coverage_map.items(), key=lambda x: x[1])

        # Find modules below threshold
        below_threshold = [
            (mod, cov) for mod, cov in coverage_map.items() if cov < threshold
        ]

        # Calculate stats
        total_modules = len(coverage_map)
        below_threshold_count = len(below_threshold)
        below_50 = sum(1 for cov in coverage_map.values() if cov < 50)

        return {
            "below_threshold": below_threshold,
            "sorted_lowest": sorted_modules[:20],
            "stats": {
                "total": total_modules,
                "below_threshold": below_threshold_count,
                "below_50": below_50,
                "threshold": threshold,
            },
        }

    # ID: 9c458310-c4b0-41ad-ad9a-10ec65d23b53
    def prioritize_files(
        self, pattern: str, max_coverage: float = 100.0, limit: int = 10
    ) -> list[tuple[str, float]]:
        """
        Get prioritized file list for test generation.

        Args:
            pattern: File glob pattern (not used, kept for interface compatibility)
            max_coverage: Only include files at or below this coverage
            limit: Maximum number of files to return

        Returns:
            List of (module_path, coverage) tuples, sorted by lowest coverage first
        """
        coverage_map = self.get_coverage_map()

        # Filter by max_coverage
        eligible = [
            (mod, cov) for mod, cov in coverage_map.items() if cov <= max_coverage
        ]

        # Sort by coverage (lowest first) and limit
        prioritized = sorted(eligible, key=lambda x: x[1])[:limit]

        return prioritized
