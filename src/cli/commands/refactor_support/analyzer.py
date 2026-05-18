# src/cli/commands/refactor_support/analyzer.py

"""Analysis helper for refactoring candidates.

Thin client over /v1/refactor/{score,candidates,stats} (ADR-057 D2). The
API owns the ModularityChecker instance; this helper just adapts API
payloads into the legacy dict shape used by refactor.py command bodies.
"""

from __future__ import annotations

import logging
from pathlib import Path

from api.cli import CoreApiClient


logger = logging.getLogger(__name__)


# ID: 64be4c1c-7799-46cf-a22d-100234b2d301
class RefactorAnalyzer:
    """Analyzes files for refactoring opportunities via the API."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = repo_root

    # ID: 7036cd6b-f1da-4546-bb02-f86f014b82cd
    async def analyze_file(self, file_path: Path) -> dict | None:
        """Analyze a single file and return detailed metrics.

        Returns None if the file is exceptionally clean.
        """
        rel = self._relative(file_path)
        client = CoreApiClient()
        try:
            payload = await client.refactor_score(file=rel)
        except Exception as exc:
            logger.debug("refactor analyzer: score fetch failed for %s: %s", rel, exc)
            return None
        if not payload.get("found"):
            return None
        return payload.get("details") or None

    # ID: 0cd1f389-137b-4bbd-8fe8-bf3c8baee474
    async def scan_codebase(
        self, files: list[Path] | None, min_score: float
    ) -> list[dict]:
        """Return refactor candidates above `min_score`, highest score first.

        `files` is retained for call-site compatibility but ignored — the
        API scans the canonical src/ tree server-side.
        """
        _ = files
        client = CoreApiClient()
        payload = await client.refactor_candidates(min_score=min_score, limit=500)
        candidates = []
        for c in payload.get("candidates", []):
            file_path = Path(c.get("file", ""))
            if self.repo_root is not None:
                file_path = (self.repo_root / file_path).resolve()
            candidates.append(
                {
                    "file": file_path,
                    "score": float(c.get("score", 0.0)),
                    "resp": int(c.get("responsibility_count", 0)),
                    "loc": int(c.get("lines_of_code", 0)),
                }
            )
        return candidates

    # ID: 412727a0-6221-4cd8-8b54-591b1f199374
    async def collect_scores(self, files: list[Path] | None) -> list[float]:
        """Collect all scores for statistical analysis.

        `files` is retained for call-site compatibility but ignored — the
        API delivers the codebase-wide score histogram server-side.
        """
        _ = files
        client = CoreApiClient()
        payload = await client.refactor_stats()
        # The stats endpoint returns histogram buckets rather than raw scores;
        # we expand the histogram to a list whose length matches `count`. This
        # preserves caller expectations (len, mean, max), at the cost of
        # losing per-score fidelity. Adequate for the stats command's display.
        histogram = payload.get("histogram") or {}
        scores: list[float] = []
        bucket_midpoints = {
            "0-20": 10.0,
            "20-40": 30.0,
            "40-60": 50.0,
            "60-80": 70.0,
            "80+": 90.0,
        }
        for bucket, count in histogram.items():
            mid = bucket_midpoints.get(bucket, 0.0)
            scores.extend([mid] * int(count))
        return scores

    def _relative(self, file_path: Path) -> str:
        """Return a repo-relative POSIX path for the API."""
        if self.repo_root is not None:
            try:
                return str(file_path.relative_to(self.repo_root)).replace("\\", "/")
            except ValueError:
                pass
        return str(file_path).replace("\\", "/")
