# src/will/agents/resource_selector.py

"""
Mind Reader: Applies constitutional rules for resource selection.
Stateless - just applies rules from Mind to select best resource.
"""

from __future__ import annotations

import json

from shared.infrastructure.database.models import CognitiveRole, LlmResource
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 208f325a-f664-4f3d-9ad3-7b481e1414f9
class ResourceSelector:
    """
    Stateless rule applier: Given roles and resources from Mind,
    select the best match based on constitutional rules.
    """

    @staticmethod
    # ID: 3398db27-785f-4e20-bf33-bd962c8ef8c8
    def select_resource_for_role(
        role_name: str, roles: list[CognitiveRole], resources: list[LlmResource]
    ) -> LlmResource | None:
        """
        Apply Mind rules to select resource for role.
        Pure function - no state, no side effects.
        """
        role = next((r for r in roles if r.role == role_name), None)
        if not role:
            logger.error("Role '%s' not found in Mind", role_name)
            return None
        if role.assigned_resource:
            resource = next(
                (r for r in resources if r.name == role.assigned_resource), None
            )
            if resource:
                logger.info(
                    "Using assigned resource '%s' for '%s'", resource.name, role_name
                )
                return resource
        qualified = [r for r in resources if ResourceSelector._is_qualified(r, role)]
        if not qualified:
            logger.error("No qualified resources for role '%s'", role_name)
            return None
        best = min(qualified, key=ResourceSelector._score_resource)
        logger.info("Selected '{best.name}' for '%s' (lowest cost)", role_name)
        return best

    @staticmethod
    def _is_qualified(resource: LlmResource, role: CognitiveRole) -> bool:
        """Check if resource capabilities match role requirements."""
        res_caps = (
            json.loads(resource.provided_capabilities)
            if isinstance(resource.provided_capabilities, str)
            else resource.provided_capabilities or []
        )
        req_caps = (
            json.loads(role.required_capabilities)
            if isinstance(role.required_capabilities, str)
            else role.required_capabilities or []
        )
        return set(req_caps).issubset(set(res_caps))

    @staticmethod
    def _score_resource(resource: LlmResource) -> int:
        """Lower is better (cost optimization)."""
        md = (
            json.loads(resource.performance_metadata)
            if isinstance(resource.performance_metadata, str)
            else resource.performance_metadata or {}
        )
        return int(md.get("cost_rating", 3))
