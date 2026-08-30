# src/body/infrastructure/repositories/llm_resource_repository.py
"""
LlmResource Repository - first governed write path for core.llm_resources
(#821 Unit 3).

core.llm_resources is DB-authoritative (ADR-052 §1) with no YAML source of
truth. Before this repository, every row was hand-written via SQL
migration -- there was no application-layer authoring/validation surface
at all. `upsert()` validates `provided_capabilities` against the
capability taxonomy (and mirrors the table's own CHECK constraints) before
ever touching the DB, so a bad definition is rejected here rather than
surfacing only as a raw IntegrityError or an after-the-fact audit finding.

CONSTITUTIONAL (proper, non-legacy):
- Callers do NOT pass sessions around.
- Repository owns DB session lifecycle via get_session() (Body MAY import
  it directly per architecture.boundary.database_session_access).
- Repository commits its own writes (because it owns the session).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select

from shared.infrastructure.database.models import LlmResource
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.capability_taxonomy import (
    CapabilityTaxonomyError,
    load_capability_taxonomy,
)
from shared.logger import getLogger


logger = getLogger(__name__)

_REQUIRED_FIELDS = ("name", "env_prefix")
_VALID_LOCALITIES = frozenset({"local", "remote"})
_VALID_HEALTH_STATUSES = frozenset({"healthy", "degraded", "unavailable", "unknown"})

# Mutable columns upsert() may set from a definition dict. `name` is handled
# separately (primary key, immutable after creation).
_MUTABLE_FIELDS = (
    "env_prefix",
    "provided_capabilities",
    "performance_metadata",
    "is_available",
    "model_name",
    "api_url",
    "locality",
    "max_concurrent",
    "rate_limit_seconds",
    "retry_attempts",
    "retry_backoff_seconds",
    "health_status",
)


# ID: 4c8e2a6b-0f3d-4c7e-a1b5-9d3f7c1e5a8b
class LlmResourceValidationError(RuntimeError):
    """Raised when an llm_resource definition fails validation.

    Fail-closed: a definition with any violation is never partially
    written -- validation runs to completion before any DB access.
    """


# ID: 5d9f3b7c-1e6a-4d8f-b2c6-0e4a8c2f6b9d
def validate_llm_resource_definition(
    definition: dict[str, Any], canonical_capabilities: frozenset[str]
) -> list[str]:
    """Return a list of violation strings; empty means valid.

    Mirrors the DB-level CHECK constraints on core.llm_resources
    (llm_resources_locality_check, llm_resources_health_status_check,
    llm_resources_available_requires_model_name,
    llm_resources_provided_capabilities_check) plus the capability-taxonomy
    canonicality rule enforced at audit time by KnowledgeGateEngine.
    """
    violations: list[str] = []

    for field in _REQUIRED_FIELDS:
        if not definition.get(field):
            violations.append(f"missing required field: {field}")

    capabilities = definition.get("provided_capabilities", [])
    if not isinstance(capabilities, list):
        violations.append("provided_capabilities must be a list")
    else:
        bad = sorted(set(capabilities) - canonical_capabilities)
        if bad:
            violations.append(f"non-canonical provided_capabilities: {bad}")

    locality = definition.get("locality", "local")
    if locality not in _VALID_LOCALITIES:
        violations.append(
            f"locality must be one of {sorted(_VALID_LOCALITIES)}, got {locality!r}"
        )

    health_status = definition.get("health_status")
    if health_status is not None and health_status not in _VALID_HEALTH_STATUSES:
        violations.append(
            f"health_status must be one of {sorted(_VALID_HEALTH_STATUSES)} "
            f"or null, got {health_status!r}"
        )

    is_available = definition.get("is_available", True)
    if is_available and not definition.get("model_name"):
        violations.append("model_name is required when is_available is true")

    return violations


# ID: 6e0a4c8d-2b5f-4e9a-c3d7-1f5b9d3a7c0e
class LlmResourceRepository:
    """
    Repository for core.llm_resources database operations.

    Proper pattern:
        async with LlmResourceRepository.open() as repo:
            resource = await repo.upsert(definition)
    """

    def __init__(self, session: Any):
        self._session = session

    @classmethod
    @asynccontextmanager
    # ID: 7f1b5d9f-3c6a-4f0b-d4e8-2a6c0e4b8d1f
    async def open(cls) -> AsyncIterator[LlmResourceRepository]:
        async with get_session() as session:
            yield cls(session)

    # ID: 8a2c6e0a-4d7b-4a1c-e5f9-3b7d1f5a9c2f
    async def get(self, name: str) -> LlmResource | None:
        """Return the row for `name`, or None if it doesn't exist."""
        result = await self._session.execute(
            select(LlmResource).where(LlmResource.name == name)
        )
        return result.scalar_one_or_none()

    # ID: 9b3d7f1b-5e8c-4b2d-f6a0-4c8e2a6b0d3a
    async def upsert(self, definition: dict[str, Any]) -> LlmResource:
        """Validate and create-or-update a core.llm_resources row.

        Raises LlmResourceValidationError fail-closed on any violation --
        including a non-canonical provided_capabilities value or an
        unreadable capability taxonomy -- never writes a partially-invalid
        row. Commits internally because this repository owns the session
        lifecycle.
        """
        try:
            canonical = load_capability_taxonomy()
        except CapabilityTaxonomyError as exc:
            raise LlmResourceValidationError(
                f"capability taxonomy unreadable: {exc}"
            ) from exc

        violations = validate_llm_resource_definition(definition, canonical)
        if violations:
            raise LlmResourceValidationError("; ".join(violations))

        existing = await self.get(definition["name"])
        if existing is not None:
            for field in _MUTABLE_FIELDS:
                if field in definition:
                    setattr(existing, field, definition[field])
            resource = existing
        else:
            resource = LlmResource(
                name=definition["name"],
                **{f: definition[f] for f in _MUTABLE_FIELDS if f in definition},
            )
            self._session.add(resource)

        await self._session.flush()
        await self._session.commit()

        logger.info("llm_resource upserted: %s", definition["name"])
        return resource
