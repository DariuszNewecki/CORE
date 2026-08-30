# src/body/atomic/llm_resource_authoring_actions.py
"""
llm_resources authoring/validation surface (#821 Unit 3).

core.llm_resources is DB-authoritative (ADR-052 §1) with no YAML source.
Before this action, there was no application-layer way to author or
validate a resource row at all -- every row was hand-written via SQL
migration. write=False validates a definition (required fields, CHECK-
constraint-equivalent rules, capability-taxonomy canonicality) without
touching the DB. write=True validates then persists via
LlmResourceRepository.upsert() (create-or-update by name).

Deliberately separate from project.cognitive_roles (#821 Unit 2) rather
than a shared "taxonomy sync" abstraction: cognitive roles flow
constitutional-source -> operational-projection; llm_resources flow
DB-authoritative-data -> constitutionally-validated-on-write. Different
authority shape, by design (this session's governor ruling).
"""

from __future__ import annotations

import time
from typing import Any

from body.atomic.registry import ActionCategory, register_action
from body.infrastructure.repositories.llm_resource_repository import (
    LlmResourceRepository,
    LlmResourceValidationError,
    validate_llm_resource_definition,
)
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.intent.capability_taxonomy import (
    CapabilityTaxonomyError,
    load_capability_taxonomy,
)
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0c4e8a2c-6b9f-4d3e-a7c1-5b9d3f7a1e4c
def _serialize(resource: Any) -> dict[str, Any]:
    """JSON-friendly dict of the persisted LlmResource row."""
    return {
        "name": resource.name,
        "env_prefix": resource.env_prefix,
        "provided_capabilities": list(resource.provided_capabilities or []),
        "performance_metadata": resource.performance_metadata,
        "is_available": resource.is_available,
        "model_name": resource.model_name,
        "api_url": resource.api_url,
        "locality": resource.locality,
        "max_concurrent": resource.max_concurrent,
        "rate_limit_seconds": resource.rate_limit_seconds,
        "retry_attempts": resource.retry_attempts,
        "retry_backoff_seconds": resource.retry_backoff_seconds,
        "health_status": resource.health_status,
        "last_health_check_at": (
            resource.last_health_check_at.isoformat()
            if resource.last_health_check_at
            else None
        ),
        "registered_at": (
            resource.registered_at.isoformat() if resource.registered_at else None
        ),
    }


@register_action(
    action_id="author.llm_resource",
    description=("Validate or persist a core.llm_resources definition (#821 Unit 3)"),
    category=ActionCategory.STATE,
    policies=["rules/ai/capability_taxonomy_governance"],
    requires_db=True,
    remediates=[],
)
@atomic_action(
    action_id="author.llm_resource",
    intent="Validate (write=False) or persist (write=True) an llm_resources definition",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 1d5f9b3d-7c0a-4e6b-b8d2-6c0e4a8c2f6b
async def action_author_llm_resource(
    core_context: CoreContext,
    write: bool = False,
    definition: dict[str, Any] | None = None,
    **kwargs,
) -> ActionResult:
    """Validate (write=False) or validate-and-persist (write=True) an llm_resources row."""
    start = time.time()

    if not definition:
        return ActionResult(
            action_id="author.llm_resource",
            ok=False,
            data={"error": "definition is required"},
            duration_sec=time.time() - start,
        )

    try:
        canonical = load_capability_taxonomy()
    except CapabilityTaxonomyError as exc:
        logger.error("author.llm_resource: capability taxonomy unreadable: %s", exc)
        return ActionResult(
            action_id="author.llm_resource",
            ok=False,
            data={"error": str(exc), "reason": "capability_taxonomy_unreadable"},
            duration_sec=time.time() - start,
        )

    violations = validate_llm_resource_definition(definition, canonical)

    if not write:
        return ActionResult(
            action_id="author.llm_resource",
            ok=not violations,
            data={
                "valid": not violations,
                "violations": violations,
                "name": definition.get("name"),
                "dry_run": True,
            },
            duration_sec=time.time() - start,
        )

    if violations:
        return ActionResult(
            action_id="author.llm_resource",
            ok=False,
            data={
                "valid": False,
                "violations": violations,
                "name": definition.get("name"),
                "dry_run": False,
            },
            duration_sec=time.time() - start,
        )

    try:
        async with LlmResourceRepository.open() as repo:
            resource = await repo.upsert(definition)
    except LlmResourceValidationError as exc:
        # Re-validated inside upsert() against a freshly-loaded taxonomy --
        # a race between this action's check above and upsert()'s own check
        # (e.g. the taxonomy file changed mid-request) fails closed here too.
        return ActionResult(
            action_id="author.llm_resource",
            ok=False,
            data={"error": str(exc), "reason": "validation_failed"},
            duration_sec=time.time() - start,
        )
    except Exception as exc:
        logger.exception("author.llm_resource: failed for %s", definition.get("name"))
        return ActionResult(
            action_id="author.llm_resource",
            ok=False,
            data={"error": str(exc), "error_type": type(exc).__name__},
            duration_sec=time.time() - start,
        )

    return ActionResult(
        action_id="author.llm_resource",
        ok=True,
        data={"valid": True, "dry_run": False, "resource": _serialize(resource)},
        duration_sec=time.time() - start,
    )
