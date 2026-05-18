# src/cli/commands/coverage/services/gaps_analyzer.py
"""Service for analyzing coverage gaps and identifying low-coverage modules.

Thin client over GET /v1/coverage/gaps (ADR-057 D1). The API owns the
CoverageAnalyzer instance server-side; this CLI service just shapes the
response for callers expecting the legacy below_threshold / sorted_lowest
/ stats layout.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from api.cli import CoreApiClient


logger = logging.getLogger(__name__)


_DEFAULT_GAP_THRESHOLD_PCT = 75.0
_DEFAULT_LOW_BUCKET_PCT = 50.0
_SORTED_LOWEST_LIMIT = 20


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class GapsAnalyzer:
    """Analyzes coverage data to identify gaps and priorities."""

    def __init__(self, repo_root: Path):
        # repo_root retained for call-site compatibility.
        self.repo_root = repo_root

    # ID: c902f595-d5bb-491e-94ea-cff937370d27
    async def get_coverage_map(self) -> dict[str, float]:
        """Get coverage percentage for all modules.

        Fetches a generous gap list (threshold=100 returns all modules)
        and projects to file→coverage. The /coverage/gaps endpoint is
        the only one that exposes per-module coverage; a dedicated
        /coverage/map endpoint would be cleaner but isn't in scope.
        """
        client = CoreApiClient()
        payload = await client.coverage_gaps(threshold=100.0, limit=10_000)
        gaps = payload.get("gaps", [])
        return {g["file"]: float(g["coverage"]) for g in gaps}

    # ID: 9ac607c3-502e-4cd1-9349-26fe7044d996
    async def find_gaps(
        self, threshold: float = _DEFAULT_GAP_THRESHOLD_PCT
    ) -> dict[str, Any]:
        """Find modules below coverage threshold.

        Args:
            threshold: Coverage percentage threshold (0-100)

        Returns:
            dict with keys:
                - below_threshold: list of (module, coverage) tuples
                - sorted_lowest: list of lowest 20 modules
                - stats: summary statistics
        """
        coverage_map = await self.get_coverage_map()

        if not coverage_map:
            return {
                "below_threshold": [],
                "sorted_lowest": [],
                "stats": {"total": 0, "below_threshold": 0, "below_50": 0},
            }

        sorted_modules = sorted(coverage_map.items(), key=lambda x: x[1])
        below_threshold = [
            (mod, cov) for mod, cov in coverage_map.items() if cov < threshold
        ]

        total_modules = len(coverage_map)
        below_threshold_count = len(below_threshold)
        below_50 = sum(
            1 for cov in coverage_map.values() if cov < _DEFAULT_LOW_BUCKET_PCT
        )

        return {
            "below_threshold": below_threshold,
            "sorted_lowest": sorted_modules[:_SORTED_LOWEST_LIMIT],
            "stats": {
                "total": total_modules,
                "below_threshold": below_threshold_count,
                "below_50": below_50,
                "threshold": threshold,
            },
        }

    # ID: 9c458310-c4b0-41ad-ad9a-10ec65d23b53
    async def prioritize_files(
        self, pattern: str, max_coverage: float = 100.0, limit: int = 10
    ) -> list[tuple[str, float]]:
        """Get prioritized file list for test generation.

        Args:
            pattern: File glob pattern (not used, kept for interface compatibility)
            max_coverage: Only include files at or below this coverage
            limit: Maximum number of files to return

        Returns:
            List of (module_path, coverage) tuples, sorted by lowest coverage first
        """
        _ = pattern
        coverage_map = await self.get_coverage_map()
        eligible = [
            (mod, cov) for mod, cov in coverage_map.items() if cov <= max_coverage
        ]
        return sorted(eligible, key=lambda x: x[1])[:limit]
