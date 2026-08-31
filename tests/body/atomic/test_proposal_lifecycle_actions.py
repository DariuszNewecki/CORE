# tests/body/atomic/test_proposal_lifecycle_actions.py

"""#842 Unit C: claim.proposal real-DB fixture pair.

Depth-verifies two G2 blocking rules whose `.intent/enforcement/mappings/
will/proposal_lifecycle.yaml` entries both name
`body.atomic.proposal_lifecycle_actions.action_claim_proposal` as
`enforced_by`, via two distinct checks in the same function:

- proposal_lifecycle.claim.authority_required — `claimed_by is None` guard,
  before any DB access.
- proposal_lifecycle.claim.idempotency_guard — the UPDATE's WHERE clause
  only matches status='approved'; a second claim on an already-'executing'
  row gets rowcount=0 and is rejected, backed by the
  autonomous_proposals_executing_once partial unique index (ADR-017 D1).

test_claim_with_authority_and_no_prior_claim_succeeds proves the compliant
side of *both* rules with one assertion set: a single first-time claim
with a real claimed_by is exactly the input each rule's own compliant
behavior requires (a recognised claimer identity, on a row nothing else
has claimed yet) — not a stretch shared citation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.proposal_lifecycle_actions import action_claim_proposal
from body.services.service_registry import service_registry
from shared.context import CoreContext
from shared.governance_token import authorize_execution
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.session_manager import get_session


pytestmark = [pytest.mark.integration]

_ACTION_ID = "claim.proposal"


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Match the production entry-point bootstrap so service_registry.
    session() (used internally by action_claim_proposal) acquires a live
    session against core_test inside the test."""
    service_registry.prime(get_session)


def _core_context() -> CoreContext:
    """Minimal CoreContext: action_claim_proposal never reads it (its own
    service_registry.session() call owns session acquisition) -- only the
    four constructor-required fields per ADR-128 need to be present."""
    return CoreContext(
        registry=MagicMock(),
        git_service=MagicMock(),
        knowledge_service=MagicMock(),
        file_handler=MagicMock(),
        file_service=MagicMock(),
    )


def _approved_proposal(proposal_id: str) -> AutonomousProposal:
    return AutonomousProposal(
        proposal_id=proposal_id,
        goal="#842 Unit C claim.proposal fixture",
        status="approved",
        actions=[
            {
                "action_id": "fix.format",
                "parameters": {"write": True, "file_path": "src/foo.py"},
                "order": 0,
            }
        ],
        scope={"files": ["src/foo.py"]},
        constitutional_constraints={},
        approval_required=False,
        created_at=datetime.now(UTC),
        approved_by="test-approver",
        approved_at=datetime.now(UTC),
        approval_authority="principal.governor",
    )


async def _fetch(session: AsyncSession, proposal_id: str) -> AutonomousProposal | None:
    """AutonomousProposal's primary key is `id` (a separate UUID column) --
    proposal_id is a distinct string column, so lookup needs a real query,
    not session.get() (which assumes the argument is the PK)."""
    result = await session.execute(
        select(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    return result.scalar_one_or_none()


async def _run(*, proposal_id: str, claimed_by: uuid.UUID | None):
    """Call the action under the governance token ActionExecutor would
    normally grant -- calling the decorated function directly without it
    raises GovernanceBypassError (shared.atomic_action's verify_authorization)."""
    with authorize_execution(_ACTION_ID):
        return await action_claim_proposal(
            core_context=_core_context(),
            write=True,
            proposal_id=proposal_id,
            claimed_by=claimed_by,
        )


async def test_claim_missing_claimed_by_rejected_before_any_db_write(
    db_session: AsyncSession,
) -> None:
    """proposal_lifecycle.claim.authority_required: claimed_by=None is
    rejected with no state mutation -- proposal stays 'approved'."""
    proposal_id = f"test-claim-noauth-{uuid.uuid4().hex[:8]}"
    db_session.add(_approved_proposal(proposal_id))
    await db_session.commit()

    try:
        result = await _run(proposal_id=proposal_id, claimed_by=None)

        assert result.ok is False
        assert "claimed_by is required" in result.data["error"]

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "approved", (
            "rejected claim attempt must not mutate proposal state"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()


async def test_claim_with_authority_and_no_prior_claim_succeeds(
    db_session: AsyncSession,
) -> None:
    """Compliant fixture for both rules: a recognised claimer identity
    (authority_required) claiming a row nothing else has claimed yet
    (idempotency_guard) succeeds and transitions the row to 'executing'."""
    proposal_id = f"test-claim-ok-{uuid.uuid4().hex[:8]}"
    claimer = uuid.uuid4()
    db_session.add(_approved_proposal(proposal_id))
    await db_session.commit()

    try:
        result = await _run(proposal_id=proposal_id, claimed_by=claimer)

        assert result.ok is True
        assert result.data["claimed"] is True
        assert result.data["claimed_by"] == str(claimer)

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "executing"
        assert str(row.claimed_by) == str(claimer)
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()


async def test_second_claim_on_already_claimed_proposal_rejected(
    db_session: AsyncSession,
) -> None:
    """proposal_lifecycle.claim.idempotency_guard: once a proposal is
    claimed (status='executing'), a second claim attempt gets rowcount=0
    from the WHERE status='approved' clause and is rejected -- the row's
    original claimer is left untouched."""
    proposal_id = f"test-claim-twice-{uuid.uuid4().hex[:8]}"
    first_claimer = uuid.uuid4()
    second_claimer = uuid.uuid4()
    db_session.add(_approved_proposal(proposal_id))
    await db_session.commit()

    try:
        first = await _run(proposal_id=proposal_id, claimed_by=first_claimer)
        assert first.ok is True, "precondition: first claim must succeed"

        second = await _run(proposal_id=proposal_id, claimed_by=second_claimer)

        assert second.ok is False
        assert "already claimed or not approved" in second.data["error"]

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "executing"
        assert str(row.claimed_by) == str(first_claimer), (
            "second (rejected) claim must not overwrite the first claimer"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()
