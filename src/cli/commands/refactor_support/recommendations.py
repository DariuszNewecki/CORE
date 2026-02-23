# src/body/cli/commands/refactor_support/recommendations.py

"""
Generates smart recommendations based on analysis results.
"""

from __future__ import annotations


# ID: 36f3d7ff-4832-419e-863a-7c169e8e5fe1
class RecommendationEngine:
    """Generates actionable recommendations from modularity analysis."""

    @staticmethod
    # ID: 90c40477-7955-446f-adb9-c330eadbe2d2
    def generate(details: dict) -> list[str]:
        """
        Generate recommendations based on breakdown scores.

        Returns list of recommendation strings.
        """
        recommendations = []
        breakdown = details["breakdown"]

        # Responsibilities recommendation
        if breakdown["responsibilities"] > 20:
            recommendations.append(
                "[bold]Split Module:[/bold] This file is doing too many things. "
                "Extract logic into new files."
            )

        # Cohesion recommendation
        if breakdown["cohesion"] > 12:
            recommendations.append(
                "[bold]Refine Logic:[/bold] Group related functions more tightly "
                "to improve focus."
            )

        # Coupling recommendation
        if breakdown["coupling"] > 10:
            recommendations.append(
                "[bold]Decouple:[/bold] Reduce external imports; use 'shared' "
                "services instead of direct calls."
            )

        # Size recommendation
        if details.get("lines_of_code", 0) > 400:
            recommendations.append(
                "[bold]Reduce Volume:[/bold] File is physically too long. "
                "Move helpers to 'shared/utils'."
            )

        return recommendations
