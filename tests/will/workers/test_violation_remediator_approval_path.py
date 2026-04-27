"""Integration test: ViolationRemediatorWorker._create_proposal records
approval_authority on the autonomous self-promote path.

URS Q2.A acceptance criterion (ADR-015 D6): a non-NULL approval_authority
on an autonomous-path approved proposal is queryable end-to-end.

The other two workers (TestRemediatorWorker, AutonomousProposalWorker) follow
the same pattern; landing this one integration test proves the refactor for
the family.
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


async def test_worker_persists_with_authority(db_session: AsyncSession) -> None:
    """Case F: a safe-risk proposal created by ViolationRemediatorWorker
    lands with status=approved, approved_by=autonomous_self_promote,
    approval_authority=risk_classification.safe_auto_approval.
    """
    worker = ViolationRemediatorWorker(declaration_name="violation_remediator")
    findings = [
        {
            "id": str(uuid.uuid4()),
            "payload": {
                "file_path": "src/test_fixture_for_band_b.py",
                "check_id": "workflow.ruff_format_check",
                "rule": "workflow.ruff_format_check",
            },
        }
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
        assert row.status == "approved"
        assert row.approved_by == "autonomous_self_promote"
        assert row.approval_authority == "risk_classification.safe_auto_approval"
        assert row.approved_at is not None
    finally:
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()
