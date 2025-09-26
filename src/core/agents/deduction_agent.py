# src/agents/deduction_agent.py
"""
Implements the DeductionAgent, responsible for dynamically selecting the most
efficient and effective LLM resource for a given task based on a constitutional policy.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from sqlalchemy import text

from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger

log = getLogger("deduction_agent")


# ID: bed143c4-1168-41c1-ac48-9c2ea70ffffb
class DeductionAgent:
    """
    Scores and selects the optimal LLM resource for a given task.
    This agent acts as the reasoning core for the CognitiveService.
    """

    def __init__(self):
        """Initializes the DeductionAgent. Policies are loaded from DB on first use."""
        agent_policy_content = settings.load("charter.policies.agent.agent_policy")
        self.deduction_policy = agent_policy_content.get("resource_selection", {})

        self.resource_manifest: Dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def _load_resource_manifest_from_db(self):
        """Lazily loads the LLM resource manifest from the database."""
        async with self._lock:
            if self.resource_manifest is not None:
                return

            log.debug(
                "Loading LLM resource manifest from database for DeductionAgent..."
            )
            async with get_session() as session:
                result = await session.execute(text("SELECT * FROM core.llm_resources"))
                resources = []
                for row in result:
                    # The database driver returns JSONB columns as strings.
                    # We must parse them back into Python dictionaries/lists.
                    row_dict = dict(row._mapping)
                    if isinstance(row_dict.get("performance_metadata"), str):
                        row_dict["performance_metadata"] = json.loads(
                            row_dict["performance_metadata"]
                        )
                    # --- THIS IS THE FIX ---
                    if isinstance(row_dict.get("provided_capabilities"), str):
                        row_dict["provided_capabilities"] = json.loads(
                            row_dict["provided_capabilities"]
                        )
                    # --- END OF FIX ---
                    resources.append(row_dict)

            self.resource_manifest = {"llm_resources": resources}
            log.debug(f"Loaded {len(resources)} LLM resources from DB.")

    def _calculate_score(
        self, resource_metadata: Dict[str, Any], weights: Dict[str, float]
    ) -> float:
        """
        Calculates a weighted score for a single LLM resource.
        Normalizes ratings (1-5 scale) before applying weights.
        """
        score = 0.0
        normalized_cost = (resource_metadata.get("cost_rating", 3) - 1) / 4
        normalized_speed = (resource_metadata.get("speed_rating", 3) - 1) / 4
        normalized_quality = (resource_metadata.get("quality_rating", 3) - 1) / 4
        normalized_reasoning = (resource_metadata.get("reasoning_rating", 3) - 1) / 4

        score += (1 - normalized_cost) * weights.get("cost", 0)
        score += normalized_speed * weights.get("speed", 0)
        score += normalized_quality * weights.get("quality", 0)
        score += normalized_reasoning * weights.get("reasoning", 0)

        return score

    # ID: 01b55061-647f-497e-9865-6fd952556b85
    async def select_best_resource(
        self, task_context: Dict[str, Any] | None = None
    ) -> str:
        """
        Selects the best LLM resource based on the deduction policy and task context.
        """
        await self._load_resource_manifest_from_db()

        task_context = task_context or {}
        role_config = task_context.get("role_config", {})
        role_name = role_config.get("role", "UnknownRole")
        role_description = role_config.get("description", "")

        # --- THIS IS THE FIX for the CognitiveService side ---
        # The required capabilities from the roles table might also be a JSON string
        required_caps_raw = role_config.get("required_capabilities", [])
        if isinstance(required_caps_raw, str):
            required_caps = set(json.loads(required_caps_raw))
        else:
            required_caps = set(required_caps_raw)
        # --- END OF FIX ---

        weights = self.deduction_policy.get("scoring_weights", {})
        overrides = self.deduction_policy.get("task_specific_overrides", [])

        search_text = (role_name + " " + role_description).lower()

        for override in overrides:
            for keyword in override.get("task_keywords", []):
                if keyword.lower() in search_text:
                    weights = override.get("weights", weights)
                    log.debug(
                        f"Applied task-specific scoring weights for role '{role_name}' "
                        f"based on keyword '{keyword}'."
                    )
                    break
            else:
                continue
            break

        resources = self.resource_manifest.get("llm_resources", [])
        if not resources:
            raise ValueError("No LLM resources defined in the database.")

        scored_resources = []
        for resource in resources:
            provided_caps = set(resource.get("provided_capabilities", []))
            if not required_caps.issubset(provided_caps):
                log.debug(
                    f"Skipping resource '{resource['name']}' due to missing "
                    f"capabilities for role '{role_name}'. Required: {required_caps - provided_caps}"
                )
                continue

            metadata = resource.get("performance_metadata")
            if not metadata:
                continue

            score = self._calculate_score(metadata, weights)
            scored_resources.append((resource["name"], score))
            log.debug(f"Scored resource '{resource['name']}': {score:.4f}")

        if not scored_resources:
            raise ValueError(f"No suitable LLM resources found for role '{role_name}'.")

        best_resource = max(scored_resources, key=lambda item: item[1])
        log.info(
            f"Deduction complete. Best resource for role '{role_name}': "
            f"'{best_resource[0]}' (Score: {best_resource[1]:.4f})"
        )
        return best_resource[0]
