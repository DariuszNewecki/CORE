# src/will/agents/resource_selector.py

"""
Mind Reader: Applies constitutional rules for resource selection.
Stateless - just applies rules from Mind to select best resource.
"""

from __future__ import annotations

import json

from shared.infrastructure.database.models import (
    CognitiveRole,
    LlmResource,
    RoleResourceAssignment,
)
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
        role_name: str,
        roles: list[CognitiveRole],
        resources: list[LlmResource],
        assignments: list[RoleResourceAssignment] | None = None,
        system_operating_mode: str = "local_only",
    ) -> LlmResource | None:
        """
        Apply Mind rules to select resource for role.
        Pure function - no state, no side effects.

        ADR-052 Phase 3: the role→resource override now arrives via
        ``assignments`` (the role_resource_assignments table), not via
        the dropped ``cognitive_roles.assigned_resource`` column. The
        primary assignment is the active row at ``priority=1`` for the
        role. When ``assignments`` is ``None`` or empty, the selector
        falls back to qualified-by-capability scoring.

        ADR-052 principle #6 (#333): resources are filtered by locality
        against the effective operating mode — ``role.operating_mode``
        if set, otherwise ``system_operating_mode`` — before any
        assignment lookup or capability check.
        """
        role = next((r for r in roles if r.role == role_name), None)
        if not role:
            logger.error("Role '%s' not found in Mind", role_name)
            return None

        effective_mode = role.operating_mode or system_operating_mode
        resources = ResourceSelector._filter_by_locality(
            resources, effective_mode, role_name
        )
        if not resources:
            logger.error(
                "No resources match locality for role '%s' under operating_mode='%s'",
                role_name,
                effective_mode,
            )
            return None

        primary = _primary_assignment(role_name, assignments)
        if primary is not None:
            resource = next((r for r in resources if r.name == primary), None)
            if resource:
                logger.debug(
                    "Using assigned resource '%s' for '%s'", resource.name, role_name
                )
                return resource

        qualified = [r for r in resources if ResourceSelector._is_qualified(r, role)]
        if not qualified:
            logger.error("No qualified resources for role '%s'", role_name)
            return None
        best = min(qualified, key=ResourceSelector._score_resource)
        logger.info("Selected '%s' for '%s' (lowest cost)", best.name, role_name)
        return best

    @staticmethod
    # ID: d4e7b2a9-3c5f-4862-9d1c-7e8b5a2f4c6d
    def select_resources_for_role(
        role_name: str,
        roles: list[CognitiveRole],
        resources: list[LlmResource],
        assignments: list[RoleResourceAssignment] | None = None,
        system_operating_mode: str = "local_only",
    ) -> list[LlmResource]:
        """
        Plural counterpart to ``select_resource_for_role`` — return every
        qualified resource for the role ordered by ``_score_resource``
        (lowest cost first), with the assigned resource at position 0 if
        present and resolvable by name.

        Used by callers that need a fallback chain rather than a single
        best match. Returns an empty list if the role is unknown.

        Mirrors the singular function's semantic that an explicit
        assignment is honored even if it does not satisfy
        ``_is_qualified`` — assignment is a deliberate governor override.

        ADR-052 Phase 3: ``assignments`` (the role_resource_assignments
        table) replaces the dropped ``cognitive_roles.assigned_resource``
        column as the source of the override.

        ADR-052 principle #6 (#333): resources are filtered by locality
        against the effective operating mode — ``role.operating_mode``
        if set, otherwise ``system_operating_mode`` — before assignment
        lookup or capability scoring.
        """
        role = next((r for r in roles if r.role == role_name), None)
        if not role:
            logger.error("Role '%s' not found in Mind", role_name)
            return []

        effective_mode = role.operating_mode or system_operating_mode
        resources = ResourceSelector._filter_by_locality(
            resources, effective_mode, role_name
        )

        qualified = [r for r in resources if ResourceSelector._is_qualified(r, role)]
        ordered = sorted(qualified, key=ResourceSelector._score_resource)

        primary = _primary_assignment(role_name, assignments)
        if primary is not None:
            assigned = next((r for r in resources if r.name == primary), None)
            if assigned:
                ordered = [assigned] + [r for r in ordered if r.name != assigned.name]

        return ordered

    @staticmethod
    # ID: 59b27757-64e3-46b6-9e51-ca01f753e48e
    def _filter_by_locality(
        resources: list[LlmResource],
        effective_mode: str,
        role_name: str,
    ) -> list[LlmResource]:
        """
        Filter ``resources`` by locality against ``effective_mode``
        (ADR-052 principle #6 / #333).

        - ``local_only``  → keep ``locality == 'local'`` only
        - ``remote_only`` → keep ``locality == 'remote'`` only
        - ``hybrid``      → keep all
        - any other mode  → fail closed; treat as ``local_only``

        Resources with ``None`` or unrecognised ``locality`` are treated
        as ``'local'`` (matches the ``server_default`` on the column).

        Excluded resource names are logged at INFO level.
        """
        kept: list[LlmResource] = []
        excluded: list[str] = []
        for r in resources:
            locality = r.locality if r.locality in ("local", "remote") else "local"
            if effective_mode == "hybrid":
                kept.append(r)
            elif effective_mode == "remote_only":
                if locality == "remote":
                    kept.append(r)
                else:
                    excluded.append(r.name)
            else:
                # local_only (default) plus any unrecognised mode fail closed to local
                if locality == "local":
                    kept.append(r)
                else:
                    excluded.append(r.name)

        if excluded:
            logger.info(
                "Locality filter excluded %d resource(s) for role '%s' "
                "under operating_mode='%s': %s",
                len(excluded),
                role_name,
                effective_mode,
                ", ".join(excluded),
            )

        return kept

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


def _primary_assignment(
    role_name: str,
    assignments: list[RoleResourceAssignment] | None,
) -> str | None:
    """Return the resource name of the active priority=1 assignment, if any."""
    if not assignments:
        return None
    for a in assignments:
        if a.role == role_name and a.priority == 1 and a.is_active:
            return a.resource
    return None
