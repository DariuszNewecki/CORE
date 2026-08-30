# src/body/atomic/cognitive_role_projection_actions.py
"""
Cognitive-role capability projection (#821 Unit 2).

`.intent/taxonomies/cognitive_roles.yaml` is constitutional and
authoritative for each role's `required_capabilities`; `core.cognitive_roles`
is a runtime projection of it. This action is the explicit, on-demand
mechanism that replaces the one-shot hand-written migration used to fix
the drift incident in commit 30adedef — no scheduled or startup-time
reconciliation (ADR-090 D1).

write=False computes and returns the diff only. write=True applies it,
UPDATE-ing required_capabilities for roles that exist (by name) in both
YAML and DB and whose capability values are all canonical. This action
never INSERTs or DELETEs a core.cognitive_roles row — a role name present
in only one side is reported, never auto-corrected; changing the role
*name* universe is a schema/CHECK-constraint migration concern (ADR-090
D2), out of this action's boundary. A YAML capability value that is not
canonical per capability_taxonomy.yaml blocks that role's row from being
written even under write=True (fail closed).

Deliberately NOT registered with `remediates=[...]`: this is a
governor-invoked CLI/API tool, not a candidate for autonomous
ViolationRemediatorWorker pickup. Drift is a reported signal; correction
is always an explicit human action, never automatic.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select, update

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.models import CognitiveRole
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.capability_taxonomy import (
    CapabilityTaxonomyError,
    load_capability_taxonomy,
)
from shared.infrastructure.intent.cognitive_roles import (
    CognitiveRolesTaxonomyError,
    load_cognitive_role_capabilities,
)
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 4f8b2e6a-1c9d-4e3a-b7f5-8a2d1c6e9f4b
def _coerce_capabilities(raw: Any) -> frozenset[str]:
    """Coerce a JSONB required_capabilities value into a frozenset[str].

    Defensive against a raw JSON-string return from the driver, matching
    the same coercion idiom used by ResourceSelector._is_qualified and
    KnowledgeGateEngine._coerce_capability_list.
    """
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return frozenset()
    if isinstance(raw, list):
        return frozenset(str(c) for c in raw)
    return frozenset()


@register_action(
    action_id="project.cognitive_roles",
    description=(
        "Diff or apply the YAML->DB projection of cognitive-role "
        "required_capabilities (#821 Unit 2)"
    ),
    category=ActionCategory.SYNC,
    policies=["rules/ai/capability_taxonomy_governance"],
    requires_db=True,
    remediates=[],
)
@atomic_action(
    action_id="project.cognitive_roles",
    intent="Project cognitive_roles.yaml required_capabilities into core.cognitive_roles",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 7c3e9a1d-5b8f-4c2e-a6d3-9f1b4e7c2a8d
async def action_project_cognitive_roles(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Diff (write=False) or apply (write=True) the cognitive-role capability projection."""
    start = time.time()

    try:
        yaml_capabilities = load_cognitive_role_capabilities()
    except CognitiveRolesTaxonomyError as exc:
        logger.error("project.cognitive_roles: YAML taxonomy unreadable: %s", exc)
        return ActionResult(
            action_id="project.cognitive_roles",
            ok=False,
            data={"error": str(exc), "reason": "yaml_taxonomy_unreadable"},
            duration_sec=time.time() - start,
        )

    try:
        canonical_capabilities = load_capability_taxonomy()
    except CapabilityTaxonomyError as exc:
        logger.error("project.cognitive_roles: capability taxonomy unreadable: %s", exc)
        return ActionResult(
            action_id="project.cognitive_roles",
            ok=False,
            data={"error": str(exc), "reason": "capability_taxonomy_unreadable"},
            duration_sec=time.time() - start,
        )

    try:
        async with get_session() as session:
            result = await session.execute(
                select(CognitiveRole.role, CognitiveRole.required_capabilities)
            )
            db_capabilities: dict[str, frozenset[str]] = {
                role: _coerce_capabilities(caps) for role, caps in result.all()
            }

            yaml_roles = set(yaml_capabilities)
            db_roles = set(db_capabilities)

            drift: list[dict[str, Any]] = []
            non_canonical: list[dict[str, Any]] = []
            for role in sorted(yaml_roles & db_roles):
                yaml_caps = yaml_capabilities[role]
                db_caps = db_capabilities[role]

                bad_caps = yaml_caps - canonical_capabilities
                if bad_caps:
                    non_canonical.append(
                        {"role": role, "capabilities": sorted(bad_caps)}
                    )
                    continue

                if yaml_caps != db_caps:
                    drift.append(
                        {
                            "role": role,
                            "yaml_capabilities": sorted(yaml_caps),
                            "db_capabilities": sorted(db_caps),
                        }
                    )

            db_only_roles = sorted(db_roles - yaml_roles)
            yaml_only_roles = sorted(yaml_roles - db_roles)
            in_sync = not drift and not non_canonical

            data: dict[str, Any] = {
                "in_sync": in_sync,
                "drift": drift,
                "db_only_roles": db_only_roles,
                "yaml_only_roles": yaml_only_roles,
                "non_canonical": non_canonical,
                "dry_run": not write,
            }

            if not write:
                return ActionResult(
                    action_id="project.cognitive_roles",
                    ok=True,
                    data=data,
                    duration_sec=time.time() - start,
                )

            applied: list[str] = []
            for entry in drift:
                role = entry["role"]
                await session.execute(
                    update(CognitiveRole)
                    .where(CognitiveRole.role == role)
                    .values(required_capabilities=entry["yaml_capabilities"])
                )
                applied.append(role)
            await session.commit()

            data["applied"] = applied
            data["blocked"] = [entry["role"] for entry in non_canonical]

            return ActionResult(
                action_id="project.cognitive_roles",
                ok=True,
                data=data,
                duration_sec=time.time() - start,
            )
    except Exception as exc:
        logger.exception("project.cognitive_roles: failed")
        return ActionResult(
            action_id="project.cognitive_roles",
            ok=False,
            data={"error": str(exc), "error_type": type(exc).__name__},
            duration_sec=time.time() - start,
        )
