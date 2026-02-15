# src/will/autonomy/proposal_state_manager.py

"""
Proposal State Manager - Lifecycle State Transitions

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Manage proposal lifecycle states
- Business logic separated from CRUD
- Uses repository for persistence

Handles state transitions:
- mark_executing, mark_completed, mark_failed
- approve, reject

Extracted from ProposalRepository to separate state management concerns.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update

from shared.logger import getLogger
from will.autonomy.proposal import ProposalStatus


logger = getLogger(__name__)


# ID: fb67abd2-1f56-43af-9c0b-2f54ffbf3355
# ID: 5a6b7c8d-9e0f-1a2b-3c4d-5e6f7a8b9c0d
class ProposalStateManager:
    """
    Manages proposal lifecycle state transitions.

    Enforces valid state changes and updates timestamps appropriately.
    """

    def __init__(self, session: Any):
        self._session = session

    # -------------------------
    # Execution State Transitions
    # -------------------------

    # ID: 76b729e6-74af-4731-b486-c3d5a75ed623
    # ID: 51be5977-1729-407c-9c47-018a565d56c4
    async def mark_executing(self, proposal_id: str) -> None:
        """Mark proposal as currently executing."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(
                status=ProposalStatus.EXECUTING.value,
                execution_started_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.info("Marked proposal as executing: %s", proposal_id)

    # ID: d572c370-8784-4e04-9ba3-4b001da73503
    # ID: 360b7769-23e8-416d-875b-45e8d3c8194c
    async def mark_completed(self, proposal_id: str, results: dict[str, Any]) -> None:
        """Mark proposal as successfully completed."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(
                status=ProposalStatus.COMPLETED.value,
                execution_completed_at=datetime.now(UTC),
                execution_results=results,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.info("Marked proposal as completed: %s", proposal_id)

    # ID: 8f4bffaf-01a0-49d6-9435-062fdaffa255
    # ID: 2f596c85-0d22-4de4-b919-791346cdb6aa
    async def mark_failed(self, proposal_id: str, reason: str) -> None:
        """Mark proposal as failed with reason."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(
                status=ProposalStatus.FAILED.value,
                execution_completed_at=datetime.now(UTC),
                failure_reason=reason,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.error("Marked proposal as failed: %s - %s", proposal_id, reason)

    # -------------------------
    # Approval State Transitions
    # -------------------------

    # ID: 7dcbf49e-72ef-4d23-9a21-5690b3811ddf
    # ID: befa870d-148c-4f53-9c31-614380e93673
    async def approve(self, proposal_id: str, approved_by: str) -> None:
        """Approve proposal for execution."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(
                status=ProposalStatus.APPROVED.value,
                approved_by=approved_by,
                approved_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.info("Approved proposal: %s by %s", proposal_id, approved_by)

    # ID: e45beb8f-5546-49f5-83cd-67217e266112
    # ID: dbdfc785-73e1-47c5-a886-3a2435c8dc95
    async def reject(self, proposal_id: str, reason: str) -> None:
        """Reject proposal with reason."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(
                status=ProposalStatus.REJECTED.value,
                failure_reason=reason,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.info("Rejected proposal: %s - %s", proposal_id, reason)

    # -------------------------
    # Context Manager for Session Lifecycle
    # -------------------------

    @classmethod
    # ID: eafbc456-17aa-4b5c-b0e8-ee8a697d0925
    async def with_session(cls, proposal_id: str) -> ProposalStateManager:
        """
        Create state manager with shared session.

        For use within existing repository context:
            async with ProposalRepository.open() as repo:
                manager = await ProposalStateManager.with_session(...)
        """
        # This is intentionally simple - callers should use the service_registry
        # pattern or wrap in their own context manager
        raise NotImplementedError(
            "Use ProposalStateManager(session) within an existing session context"
        )
