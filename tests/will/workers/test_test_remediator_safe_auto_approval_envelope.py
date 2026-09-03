"""#853 governor rulings 4/6, real end-to-end: TestRemediatorWorker's
flow.build_test_for_symbol proposal creator (will.workers.test_remediator
._operations._create_symbol_proposal) must preserve the proposal in DRAFT
when safe auto-approval is denied, not treat the denial as a persistence
failure.

flow.build_test_for_symbol is a FLOW (ProposalAction.flow_id, not
action_id) -- no flow is authorized for safe auto-approval, including
test-generation flows (governor ruling 4). Its underlying step
(build.test_for_symbol) is impact_level: safe, so proposal.approval_required
computes False and the worker attempts safe auto-approval; the envelope
must deny it because it is a flow, not because of anything else about the
proposal's shape.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.session_manager import get_session
from will.workers.test_remediator._operations import _create_symbol_proposal


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror the production entry-point bootstrap so service_registry.session()
    inside the module function can acquire a live session against core_test."""
    service_registry.prime(get_session)


async def test_symbol_proposal_preserves_draft_when_flow_denied_by_envelope(
    db_session: AsyncSession,
) -> None:
    source_file = f"src/test_fixture_{uuid.uuid4().hex[:8]}.py"
    test_file = f"tests/test_fixture_{uuid.uuid4().hex[:8]}.py"

    proposal_id = await _create_symbol_proposal(
        source_file=source_file,
        symbol_name="some_function",
        symbol_kind="function",
        signature="def some_function() -> None: ...",
        test_file=test_file,
        findings=[
            {
                "id": str(uuid.uuid4()),
                "payload": {"source_file": source_file, "test_file": test_file},
            }
        ],
    )

    assert proposal_id is not None, (
        "envelope denial (no flow is authorized) must not be treated as a "
        "persistence failure -- the proposal row must still be committed"
    )

    try:
        db_session.expire_all()
        result = await db_session.execute(
            select(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        row = result.scalar_one()
        assert row.status == "draft"
        assert row.approved_by is None
        assert row.approval_authority is None
    finally:
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()
