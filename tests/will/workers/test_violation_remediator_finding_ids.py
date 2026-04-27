"""Integration test: ViolationRemediatorWorker._create_proposal populates
constitutional_constraints['finding_ids'] with the blackboard entry IDs of
the consumed findings.

The proposal→finding read path at
src/will/autonomy/proposal_executor.py:265-266 reads this key when emitting
consequence-log entries; without it the consequence log loses the linkage
back to the originating findings. ADR-015 D7: forward-only, no historical
backfill — this test exists to prevent regression on the new path.
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
from will.workers.violation_remediator import ViolationRemediatorWorker


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror the production entry-point bootstrap so service_registry.session()
    inside the worker can acquire a live session against core_test.
    See src/body/infrastructure/bootstrap.py:52, src/cli/admin_cli.py:86, etc."""
    service_registry.prime(get_session)


async def test_create_proposal_records_finding_ids(
    db_session: AsyncSession,
) -> None:
    """Two synthetic findings → one proposal whose
    constitutional_constraints['finding_ids'] is a list containing the
    entry IDs of both findings (as strings, in the order received).
    """
    worker = ViolationRemediatorWorker(declaration_name="violation_remediator")

    finding_a_id = str(uuid.uuid4())
    finding_b_id = str(uuid.uuid4())
    findings = [
        {
            "id": finding_a_id,
            "payload": {
                "file_path": "src/test_fixture_for_finding_ids_a.py",
                "check_id": "workflow.ruff_format_check",
                "rule": "workflow.ruff_format_check",
            },
        },
        {
            "id": finding_b_id,
            "payload": {
                "file_path": "src/test_fixture_for_finding_ids_b.py",
                "check_id": "workflow.ruff_format_check",
                "rule": "workflow.ruff_format_check",
            },
        },
    ]

    proposal_id = await worker._create_proposal("fix.format", findings)
    assert proposal_id is not None, (
        "_create_proposal returned None — proposal was not persisted"
    )

    try:
        db_session.expire_all()
        result = await db_session.execute(
            select(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        row = result.scalar_one()

        constraints = row.constitutional_constraints
        assert "finding_ids" in constraints, (
            "constitutional_constraints missing 'finding_ids' key — "
            "the proposal→finding read path is asymmetric again"
        )
        recorded = constraints["finding_ids"]
        assert isinstance(recorded, list), (
            f"finding_ids must be a list, got {type(recorded).__name__}"
        )
        assert all(isinstance(fid, str) for fid in recorded), (
            f"finding_ids entries must all be strings, got {recorded!r}"
        )
        assert set(recorded) == {finding_a_id, finding_b_id}, (
            f"finding_ids must contain both consumed entry IDs, got {recorded!r}"
        )
    finally:
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()
