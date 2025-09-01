# src/agents/deduction_agent.py
"""
Implements the DeductionAgent, responsible for dynamically selecting the most
efficient and effective LLM resource for a given task based on a constitutional policy.
"""

from __future__ import annotations

from typing import Any, Dict

from shared.config import Settings
from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger("deduction_agent")


# CAPABILITY: agent.llm.resource_selection
class DeductionAgent:
    """
    Scores and selects the optimal LLM resource for a given task.
    This agent acts as the reasoning core for the CognitiveService.
    """

    # CAPABILITY: agents.deduction_agent.initialize
    def __init__(self, settings: Settings):
        """Initializes the DeductionAgent by loading its governing policies."""
        self.settings = settings
        self.deduction_policy = load_config(
            self.settings.MIND / "policies" / "deduction_policy.yaml"
        )
        self.resource_manifest = load_config(self.settings.RESOURCE_MANIFEST_PATH)

    # CAPABILITY: agent.llm.resource_score
    def _calculate_score(
        self, resource_metadata: Dict[str, Any], weights: Dict[str, float]
    ) -> float:
        """
        Calculates a weighted score for a single LLM resource.
        Normalizes ratings (1-5 scale) before applying weights.
        """
        score = 0.0
        # Normalize ratings from 1-5 to 0-1 for consistent scoring.
        normalized_cost = (resource_metadata.get("cost_rating", 3) - 1) / 4
        normalized_speed = (resource_metadata.get("speed_rating", 3) - 1) / 4
        normalized_quality = (resource_metadata.get("quality_rating", 3) - 1) / 4
        normalized_reasoning = (resource_metadata.get("reasoning_rating", 3) - 1) / 4

        # Cost is inverted: a lower cost rating (e.g., 1) is better.
        score += (1 - normalized_cost) * weights.get("cost", 0)
        score += normalized_speed * weights.get("speed", 0)
        score += normalized_quality * weights.get("quality", 0)
        score += normalized_reasoning * weights.get("reasoning", 0)

        return score

    # CAPABILITY: agent.llm.resource_selection
    def select_best_resource(self, task_context: Dict[str, Any] | None = None) -> str:
        """
        Selects the best LLM resource based on the deduction policy and task context.
        """
        task_context = task_context or {}
        weights = self.deduction_policy.get("scoring_weights", {})
        resources = self.resource_manifest.get("llm_resources", [])

        if not resources:
            raise ValueError("No LLM resources defined in the constitution.")

        scored_resources = []
        for resource in resources:
            metadata = resource.get("performance_metadata")
            if not metadata:
                continue

            score = self._calculate_score(metadata, weights)
            scored_resources.append((resource["name"], score))
            log.debug(f"Scored resource '{resource['name']}': {score:.4f}")

        if not scored_resources:
            raise ValueError("No scorable LLM resources defined.")

        best_resource = max(scored_resources, key=lambda item: item[1])
        log.info(
            f"Deduction complete. Best resource for the task: '{best_resource[0]}' (Score: {best_resource[1]:.4f})"
        )
        return best_resource[0]
