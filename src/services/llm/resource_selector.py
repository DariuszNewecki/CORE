# src/services/llm/resource_selector.py
"""
Provides a dedicated service for selecting the optimal LLM resource for a given cognitive role.
"""
from __future__ import annotations

from typing import List, Optional

from services.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger

log = getLogger("resource_selector")


# ID: 1b8e9c7d-6f5a-4b3e-8c7d-6f5a4b3e8c7d
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

    def _score_resource_for_role(
        self, resource: LlmResource, role: CognitiveRole
    ) -> Optional[int]:
        """
        Scores a resource for a role. Returns cost rating on match, else None.
        Lower score is better (cheaper).
        """
        res_caps = set(resource.provided_capabilities or [])
        req_caps = set(role.required_capabilities or [])

        if not req_caps.issubset(res_caps):
            return None  # Does not meet capability requirements

        md = resource.performance_metadata or {}
        cost = md.get("cost_rating")

        # Default to a medium cost if not specified
        return int(cost) if isinstance(cost, (int, float)) else 3

    # ID: 2c7d6f5a-4b3e-8c7d-6f5a4b3e8c7e
    # ID: a4ec1377-c50c-46df-842a-14b7bfebf675
    def select_resource_for_role(self, role_name: str) -> Optional[LlmResource]:
        """
        Selects the best (lowest cost) resource that satisfies the capabilities for a given role.
        """
        role = self.roles_by_name.get(role_name)
        if not role:
            log.error(f"Cannot select resource: Role '{role_name}' not found.")
            return None

        candidates = []
        for resource in self.resources:
            score = self._score_resource_for_role(resource, role)
            if score is not None:
                candidates.append((score, resource))

        if not candidates:
            log.warning(f"No suitable resource found for role '{role_name}'.")
            return None

        # Sort by score (cost), lowest first
        candidates.sort(key=lambda x: x[0])
        best_resource = candidates[0][1]

        log.info(f"Selected resource '{best_resource.name}' for role '{role_name}'.")
        return best_resource
