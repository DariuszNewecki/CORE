# tests/body/atomic/test_cognitive_role_projection_actions.py
"""#821 Unit 2: project.cognitive_roles atomic action.

DB-integration tests against the live core.cognitive_roles table (excluded
from the autouse TRUNCATE-between-tests fixture per tests/conftest.py,
since it is shared config/registry state read by other tests and by
ResourceSelector at runtime). Every test that mutates a row restores its
original required_capabilities in a `finally` block so the shared table
is left exactly as found, regardless of test outcome.

core_test is schema-only in CI (no seed data, mirroring
tests/shared/infrastructure/test_task_assignee_roles_schema.py's own
documented caveat) -- _TARGET_ROLE may not exist there at all. The
autouse `_ensure_target_role_present` fixture idempotently seeds it with
its *current YAML-declared* capabilities only if the row is missing,
never overwriting a real row's data, so the same tests prove the same
property whether run against a schema-only core_test or a dev DB that
already carries live data.

CAUTION: this file performs real UPDATEs against core.cognitive_roles
(the write=True / --apply path). Per CLAUDE.md, running a test file known
to hit shared live state is governor-initiated -- do not run this file
without asking first, even though writing it is a normal part of the
change.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.cognitive_role_projection_actions import (
    action_project_cognitive_roles,
)
from shared.context import CoreContext
from shared.governance_token import authorize_execution
from shared.infrastructure.database.models import CognitiveRole
from shared.infrastructure.intent.cognitive_roles import (
    load_cognitive_role_capabilities,
)


pytestmark = [pytest.mark.integration]

_ACTION_ID = "project.cognitive_roles"

# Vectorizer's real YAML declaration (verified live: {"embedding"}) is
# deliberately not hardcoded here -- tests read whatever the YAML
# currently says and restore whatever the DB currently holds, so they
# stay correct even if either drifts later.
_TARGET_ROLE = "Vectorizer"


def _core_context() -> CoreContext:
    """Minimal CoreContext for this action: it never reads core_context at
    all (get_session() owns its own session acquisition), so every
    mandatory field is a MagicMock -- only the four constructor-required
    fields per ADR-128 need to be present."""
    return CoreContext(
        registry=MagicMock(),
        git_service=MagicMock(),
        knowledge_service=MagicMock(),
        file_handler=MagicMock(),
        file_service=MagicMock(),
    )


async def _run(*, write: bool):
    """Call the action under the governance token ActionExecutor would
    normally grant -- calling the decorated function directly without it
    raises GovernanceBypassError (shared.atomic_action's verify_authorization)."""
    with authorize_execution(_ACTION_ID):
        return await action_project_cognitive_roles(
            core_context=_core_context(), write=write
        )


@pytest.fixture(autouse=True)
# ID: 2a5c9e3f-6b1d-4a7c-9e3f-8b2d5a9c1e6f
async def _ensure_target_role_present(db_session: AsyncSession) -> None:
    """Idempotent seed: insert _TARGET_ROLE with its current YAML-declared
    capabilities only if the row doesn't already exist. Never overwrites a
    real row (ON CONFLICT DO NOTHING), so a dev DB's live data is untouched
    and a schema-only core_test gets a healthy baseline to test against."""
    yaml_caps = sorted(load_cognitive_role_capabilities()[_TARGET_ROLE])
    await db_session.execute(
        text(
            "INSERT INTO core.cognitive_roles (role, required_capabilities) "
            "VALUES (:role, CAST(:caps AS jsonb)) "
            "ON CONFLICT (role) DO NOTHING"
        ),
        {"role": _TARGET_ROLE, "caps": json.dumps(yaml_caps)},
    )
    await db_session.commit()


@pytest.fixture
# ID: 6a1d5f9b-3c7e-4a2f-9d6b-0e4a8c2f6b1d
async def _restore_target_role(
    db_session: AsyncSession, _ensure_target_role_present: None
):
    """Snapshot _TARGET_ROLE's required_capabilities and restore it after the test."""
    result = await db_session.execute(
        select(CognitiveRole.required_capabilities).where(
            CognitiveRole.role == _TARGET_ROLE
        )
    )
    original = result.scalar_one()
    try:
        yield original
    finally:
        await db_session.execute(
            update(CognitiveRole)
            .where(CognitiveRole.role == _TARGET_ROLE)
            .values(required_capabilities=original)
        )
        await db_session.commit()


# ID: 7b2e6a0c-4d8f-4b3a-a0c7-1f5b9d3a7e2c
async def test_diff_reports_in_sync_when_no_drift(db_session: AsyncSession) -> None:
    """With no induced drift, write=False reports no entries for the target role."""
    result = await _run(write=False)
    assert result.ok is True
    assert result.data["dry_run"] is True
    assert result.data["non_canonical"] == []
    # Not asserting in_sync globally True: a real pre-existing drift elsewhere
    # in the table would make this test environment-fragile. Assert instead
    # that our target role specifically shows no drift right now.
    drifted_roles = {entry["role"] for entry in result.data["drift"]}
    assert _TARGET_ROLE not in drifted_roles


# ID: 8c3f7b1d-5e9a-4c4b-b1d8-2a6c0e4b8f3d
async def test_apply_corrects_induced_drift_for_target_role_only(
    db_session: AsyncSession,
    _restore_target_role: Any,
) -> None:
    """Induce drift on one role; write=True corrects only that role."""
    await db_session.execute(
        update(CognitiveRole)
        .where(CognitiveRole.role == _TARGET_ROLE)
        .values(required_capabilities=["intentionally_wrong_capability_value"])
    )
    await db_session.commit()

    diff_result = await _run(write=False)
    assert diff_result.ok is True
    drift_roles = {entry["role"] for entry in diff_result.data["drift"]}
    assert _TARGET_ROLE in drift_roles

    apply_result = await _run(write=True)
    assert apply_result.ok is True
    assert _TARGET_ROLE in apply_result.data["applied"]

    verify = await db_session.execute(
        select(CognitiveRole.required_capabilities).where(
            CognitiveRole.role == _TARGET_ROLE
        )
    )
    assert "intentionally_wrong_capability_value" not in verify.scalar_one()


# ID: 9d4a8c2e-6f0b-4d5c-c2e9-3b7d1f5a9c4e
async def test_non_canonical_yaml_value_is_reported_and_never_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-canonical capability value in the (mocked) YAML side blocks
    that role from being written even under write=True -- fail closed."""
    monkeypatch.setattr(
        "body.atomic.cognitive_role_projection_actions.load_cognitive_role_capabilities",
        lambda: {_TARGET_ROLE: frozenset({"not_a_real_capability"})},
    )

    result = await _run(write=True)
    assert result.ok is True
    non_canonical_roles = {entry["role"] for entry in result.data["non_canonical"]}
    assert _TARGET_ROLE in non_canonical_roles
    assert _TARGET_ROLE not in result.data["applied"]
    assert _TARGET_ROLE in result.data["blocked"]


# ID: 0e5b9d3f-7a1c-4e6d-d3f0-4c8e2a6b0d5f
async def test_yaml_taxonomy_unreadable_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shared.infrastructure.intent.cognitive_roles import (
        CognitiveRolesTaxonomyError,
    )

    def _raise():
        raise CognitiveRolesTaxonomyError("boom")

    monkeypatch.setattr(
        "body.atomic.cognitive_role_projection_actions.load_cognitive_role_capabilities",
        _raise,
    )

    result = await _run(write=False)
    assert result.ok is False
    assert result.data["reason"] == "yaml_taxonomy_unreadable"


# ID: 1f6c0e4a-8b2d-4f7e-e4a1-5d9f3b7c1e6a
async def test_db_only_and_yaml_only_roles_are_never_mutated(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A role name present on only one side is reported, never inserted or
    deleted -- name-set changes are a schema/migration concern, not this
    action's boundary."""
    real = load_cognitive_role_capabilities()
    faked = dict(real)
    faked["TotallyMadeUpRole"] = frozenset({"reasoning"})

    monkeypatch.setattr(
        "body.atomic.cognitive_role_projection_actions.load_cognitive_role_capabilities",
        lambda: faked,
    )

    result = await _run(write=True)
    assert result.ok is True
    assert "TotallyMadeUpRole" in result.data["yaml_only_roles"]

    verify = await db_session.execute(
        select(CognitiveRole.role).where(CognitiveRole.role == "TotallyMadeUpRole")
    )
    assert verify.scalar_one_or_none() is None
