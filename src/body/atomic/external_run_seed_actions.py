# src/body/atomic/external_run_seed_actions.py
"""
seed.external_run_resources -- the ONE governed writer that populates an
isolated external-run database with runtime resources (#894 seeding unit;
Governor ruling D, 2026-09-15).

Scope, exactly as ruled:
- isolated external-run database ONLY: the primary proof is that the
  connected database's ``current_database()`` equals the run-specific
  disposable name the apparatus supplied; refusing known production and
  non-disposable-shaped names is defence in depth, not the proof;
- seed-document-driven (``shared.infrastructure.intent.external_run_seed``);
- one transaction: every row or none;
- exact closed fields only: ``core.llm_resources`` rows through the same
  validator ``author.llm_resource`` uses, ``core.role_resource_assignments``
  {role, resource, priority, is_active}, ``core.system_config``
  {operating_mode, llm_enabled};
- create-only: a database that already carries any of these rows is not
  the empty isolated database this action is for -- refuse;
- risk classification ``moderate`` (``.intent/enforcement/config/action_risk.yaml``);
  never listed in the safe-auto-approval envelope; ``write=False`` validates
  and reports without touching the database.

This action does not write ``.intent/``. Roles are NOT seeded here (ruling
E: ``project.cognitive_roles`` projects them from the bound copy's own
taxonomy). Secrets are never carried by the seed document.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import func, select, text

from body.atomic.registry import ActionCategory, register_action
from body.infrastructure.repositories.llm_resource_repository import (
    _MUTABLE_FIELDS,
    validate_llm_resource_definition,
)
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.context import CoreContext
from shared.infrastructure.database.models import (
    LlmResource,
    RoleResourceAssignment,
    SystemConfig,
)
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.capability_taxonomy import (
    CapabilityTaxonomyError,
    load_capability_taxonomy,
)
from shared.infrastructure.intent.external_run_seed import (
    SeedDocument,
    SeedError,
    validate_isolated_database_name,
)
from shared.logger import getLogger


logger = getLogger(__name__)

ACTION_ID = "seed.external_run_resources"


def _refuse(reason: str, start: float, **extra: Any) -> ActionResult:
    logger.error("%s: refused -- %s", ACTION_ID, reason)
    return ActionResult(
        action_id=ACTION_ID,
        ok=False,
        data={"error": reason, "reason": "seed_refused", **extra},
        duration_sec=time.time() - start,
    )


@register_action(
    action_id=ACTION_ID,
    description=(
        "Seed an isolated external-run database with llm_resources, "
        "role-resource assignments and system_config from a seed document "
        "(#894, ADR-159 Note 2026-09-15 ruling D)"
    ),
    category=ActionCategory.STATE,
    policies=["rules/ai/capability_taxonomy_governance"],
    requires_db=True,
    remediates=[],
)
@atomic_action(
    action_id=ACTION_ID,
    intent=(
        "Populate an isolated external-run database with the operator's seed "
        "document in one transaction; refuse any other database"
    ),
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 983d313a-36d3-4c92-8673-39a19441cd05
async def action_seed_external_run_resources(
    core_context: CoreContext,
    write: bool = False,
    seed: SeedDocument | None = None,
    expected_database: str | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Validate (write=False) or apply (write=True) a seed document to the
    isolated database named by *expected_database*."""
    start = time.time()
    if seed is None:
        return _refuse("seed document is required", start)
    if not expected_database:
        return _refuse(
            "expected_database (the run's disposable name) is required", start
        )
    try:
        validate_isolated_database_name(expected_database)
    except SeedError as exc:
        return _refuse(str(exc), start)

    try:
        canonical = load_capability_taxonomy()
    except CapabilityTaxonomyError as exc:
        return _refuse(f"capability taxonomy unreadable: {exc}", start)

    violations: dict[str, list[str]] = {}
    for definition in seed.resources:
        unknown = set(definition) - set(_MUTABLE_FIELDS) - {"name", "model_digest"}
        found = validate_llm_resource_definition(definition, canonical)
        if unknown:
            found = [*found, f"unknown fields (closed set): {sorted(unknown)}"]
        if found:
            violations[definition["name"]] = found
    if violations:
        return _refuse(
            "llm_resources definitions invalid", start, violations=violations
        )

    try:
        async with get_session() as session:
            # PRIMARY isolation proof: we are connected to exactly the database
            # the apparatus provisioned for this run -- not to whatever
            # DATABASE_URL happens to name.
            current = (
                await session.execute(text("SELECT current_database()"))
            ).scalar_one()
            if current != expected_database:
                return _refuse(
                    f"connected database {current!r} is not the run's isolated "
                    f"database {expected_database!r}",
                    start,
                )
            counts = {
                "llm_resources": (
                    await session.execute(select(func.count()).select_from(LlmResource))
                ).scalar_one(),
                "role_resource_assignments": (
                    await session.execute(
                        select(func.count()).select_from(RoleResourceAssignment)
                    )
                ).scalar_one(),
                "system_config": (
                    await session.execute(
                        select(func.count()).select_from(SystemConfig)
                    )
                ).scalar_one(),
            }
            occupied = {k: v for k, v in counts.items() if v}
            if occupied:
                return _refuse(
                    "database already carries seedable rows; this action is "
                    "create-only for an empty isolated database",
                    start,
                    occupied=occupied,
                )
            # Ruling E ordering: roles come from the copy's taxonomy via
            # project.cognitive_roles and must already exist -- an assignment
            # references core.cognitive_roles(role). Refuse clearly rather
            # than fail on the foreign key.
            needed_roles = sorted({a["role"] for a in seed.assignments})
            present_roles = {
                r
                for (r,) in (
                    await session.execute(
                        text(
                            "SELECT role FROM core.cognitive_roles "
                            "WHERE role = ANY(:roles)"
                        ),
                        {"roles": needed_roles},
                    )
                ).all()
            }
            missing_roles = [r for r in needed_roles if r not in present_roles]
            if missing_roles:
                return _refuse(
                    "assignments reference roles not present in the isolated "
                    f"database: {missing_roles}; project roles first "
                    "(project.cognitive_roles, ruling E)",
                    start,
                )

            plan = {
                "database": current,
                "llm_resources": [d["name"] for d in seed.resources],
                "assignments": [
                    f"{a['role']}->{a['resource']}@{a['priority']}"
                    for a in seed.assignments
                ],
                "system_config": dict(seed.system_config),
                "dry_run": not write,
            }
            if not write:
                return ActionResult(
                    action_id=ACTION_ID,
                    ok=True,
                    data=plan,
                    duration_sec=time.time() - start,
                    impact=ActionImpact.WRITE_DATA,
                )

            for definition in seed.resources:
                session.add(
                    LlmResource(
                        name=definition["name"],
                        **{
                            f: definition[f] for f in _MUTABLE_FIELDS if f in definition
                        },
                    )
                )
            # Resources first: assignments carry a DB-level FK to
            # llm_resources(name) that no ORM relationship orders for us.
            await session.flush()
            for a in seed.assignments:
                session.add(
                    RoleResourceAssignment(
                        role=a["role"],
                        resource=a["resource"],
                        priority=a["priority"],
                        is_active=a["is_active"],
                    )
                )
            session.add(
                SystemConfig(
                    operating_mode=seed.system_config["operating_mode"],
                    llm_enabled=seed.system_config["llm_enabled"],
                )
            )
            await session.flush()
            await session.commit()
            plan["dry_run"] = False
            return ActionResult(
                action_id=ACTION_ID,
                ok=True,
                data=plan,
                duration_sec=time.time() - start,
                impact=ActionImpact.WRITE_DATA,
            )
    except Exception as exc:  # one transaction: any failure rolls everything back
        logger.exception("%s: failed", ACTION_ID)
        return ActionResult(
            action_id=ACTION_ID,
            ok=False,
            data={"error": str(exc), "error_type": type(exc).__name__},
            duration_sec=time.time() - start,
        )
