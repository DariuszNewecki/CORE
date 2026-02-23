# src/body/cli/commands/refactor_support/analyzer.py

"""
Analysis logic for refactoring candidates.
"""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker


# ID: 64be4c1c-7799-46cf-a22d-100234b2d301
class RefactorAnalyzer:
    """Analyzes files for refactoring opportunities."""

    def __init__(self):
        self.checker = ModularityChecker()

    # ID: 7036cd6b-f1da-4546-bb02-f86f014b82cd
    def analyze_file(self, file_path: Path) -> dict | None:
        """
        Analyze a single file and return detailed metrics.

        Returns None if file is exceptionally clean.
        """
        findings = self.checker.check_refactor_score(file_path, {"max_score": 0})

        if not findings:
            return None

        return findings[0]["details"]

    # ID: 0cd1f389-137b-4bbd-8fe8-bf3c8baee474
    def scan_codebase(self, files: list[Path], min_score: float) -> list[dict]:
        """
        Scan multiple files and return candidates above threshold.

        Returns sorted list (highest scores first).
        """
        candidates = []

        for file in files:
            try:
                details = self.analyze_file(file)
                if details and details["total_score"] >= min_score:
                    candidates.append(
                        {
                            "file": file,
                            "score": details["total_score"],
                            "resp": details["responsibility_count"],
                            "loc": details.get("lines_of_code", 0),
                        }
                    )
            except Exception:
                continue

        # Sort by score (highest first)
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    # ID: 412727a0-6221-4cd8-8b54-591b1f199374
    def collect_scores(self, files: list[Path]) -> list[float]:
        """Collect all scores for statistical analysis."""
        scores = []

        for file in files:
            try:
                details = self.analyze_file(file)
                if details:
                    scores.append(details["total_score"])
            except Exception:
                continue

        return scores
