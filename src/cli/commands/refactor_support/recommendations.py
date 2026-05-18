# src/cli/commands/refactor_support/recommendations.py

"""Generates smart recommendations based on analysis results.

Pure presentation/text helper. Thresholds are baked in as CLI defaults
rather than reaching into `shared.infrastructure.intent.operational_config`;
the recommendation surface is governor-tuned only when copy changes, not
on operational drift.
"""

from __future__ import annotations


_RESPONSIBILITIES_THRESHOLD = 20.0
_COHESION_THRESHOLD = 15.0
_COUPLING_THRESHOLD = 15.0
_LOC_THRESHOLD = 400


# ID: 36f3d7ff-4832-419e-863a-7c169e8e5fe1
class RecommendationEngine:
    """Generates actionable recommendations from modularity analysis."""

    @staticmethod
    # ID: 90c40477-7955-446f-adb9-c330eadbe2d2
    def generate(details: dict) -> list[str]:
        """Generate recommendations based on breakdown scores."""
        recommendations: list[str] = []
        breakdown = details.get("breakdown", {})

        if breakdown.get("responsibilities", 0) > _RESPONSIBILITIES_THRESHOLD:
            recommendations.append(
                "[bold]Split Module:[/bold] This file is doing too many things. "
                "Extract logic into new files."
            )

        if breakdown.get("cohesion", 0) > _COHESION_THRESHOLD:
            recommendations.append(
                "[bold]Refine Logic:[/bold] Group related functions more tightly "
                "to improve focus."
            )

        if breakdown.get("coupling", 0) > _COUPLING_THRESHOLD:
            recommendations.append(
                "[bold]Decouple:[/bold] Reduce external imports; use shared "
                "services instead of direct calls."
            )

        if details.get("lines_of_code", 0) > _LOC_THRESHOLD:
            recommendations.append(
                "[bold]Reduce Volume:[/bold] File is physically too long. "
                "Move helpers to shared/utils."
            )

        return recommendations
