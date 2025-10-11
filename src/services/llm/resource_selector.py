# src/services/llm/resource_selector.py
"""
Provides a dedicated service for selecting the optimal LLM resource for a given cognitive role.
"""

from __future__ import annotations

from typing import List, Optional

from services.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger

log = getLogger("resource_selector")


# ID: b2f33e2c-4c68-46a5-9e89-a9ac80e3e0e5
class ResourceSelector:
    """
    Selects the best LLM resource based on capabilities and performance metadata.
    This service serves the 'separation_of_concerns' principle by decoupling resource
    selection from the main CognitiveService orchestration.
    """

    def __init__(self, resources: List[LlmResource], roles: List[CognitiveRole]):
        """
        Initializes the selector with the full list of available resources and roles from the database.
        """
        self.resources = resources
        self.roles = roles
        self.resources_by_name = {r.name: r for r in self.resources}
        self.roles_by_name = {r.role: r for r in self.roles}
        log.info(
            f"ResourceSelector initialized with {len(self.resources)} resources and {len(self.roles)} roles."
        )

    def _is_resource_qualified(
        self, resource: LlmResource, role: CognitiveRole
    ) -> bool:
        """Checks if a resource has the capabilities required by a role."""
        res_caps = set(resource.provided_capabilities or [])
        req_caps = set(role.required_capabilities or [])
        return req_caps.issubset(res_caps)

    def _score_resource(self, resource: LlmResource) -> int:
        """Returns the cost rating of a resource, defaulting to a medium cost."""
        md = resource.performance_metadata or {}
        cost = md.get("cost_rating")
        return int(cost) if isinstance(cost, (int, float)) else 3

    # ID: 8636a4a6-7c58-4bb0-8372-e48e9184884d
    def select_resource_for_role(self, role_name: str) -> Optional[LlmResource]:
        """
        Selects the best resource for a role, prioritizing the explicitly assigned one.
        """
        role = self.roles_by_name.get(role_name)
        if not role:
            log.error(f"Cannot select resource: Role '{role_name}' not found.")
            return None

        # --- THIS IS THE DEFINITIVE FIX ---
        # Step 1: Prioritize the explicitly assigned resource.
        assigned_resource_name = role.assigned_resource
        if assigned_resource_name:
            assigned_resource = self.resources_by_name.get(assigned_resource_name)
            if assigned_resource and self._is_resource_qualified(
                assigned_resource, role
            ):
                log.info(
                    f"Selected explicitly assigned resource '{assigned_resource.name}' for role '{role_name}'."
                )
                return assigned_resource
            else:
                log.warning(
                    f"Assigned resource '{assigned_resource_name}' for role '{role_name}' is not available or not qualified. Searching for an alternative."
                )
        # --- END OF FIX ---

        # Step 2: If the assigned one is invalid, find the best alternative.
        candidates = []
        for resource in self.resources:
            if self._is_resource_qualified(resource, role):
                score = self._score_resource(resource)
                candidates.append((score, resource))

        if not candidates:
            log.warning(f"No suitable resource found for role '{role_name}'.")
            return None

        # Sort by score (cost), lowest first
        candidates.sort(key=lambda x: x[0])
        best_alternative = candidates[0][1]

        log.info(
            f"Selected best alternative resource '{best_alternative.name}' for role '{role_name}'."
        )
        return best_alternative
