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

    # ID: 51be5977-1729-407c-9c47-018a565d56c4
    async def mark_executing(self, proposal_id: str) -> None:
        """Mark proposal as currently executing.

        Guards against concurrent execution by requiring status = 'approved' in
        the WHERE clause. Raises RuntimeError if 0 rows updated (already claimed).
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(
                AutonomousProposal.proposal_id == proposal_id,
                AutonomousProposal.status == ProposalStatus.APPROVED.value,
            )
            .values(
                status=ProposalStatus.EXECUTING.value,
                execution_started_at=datetime.now(UTC),
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            await self._session.rollback()
            raise RuntimeError(
                f"Proposal {proposal_id} was already claimed or not in approved status"
            )
        await self._session.commit()
        logger.info("Marked proposal as executing: %s", proposal_id)

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

    # ID: 2f596c85-0d22-4de4-b919-791346cdb6aa
    async def mark_failed(
        self,
        proposal_id: str,
        reason: str,
        results: dict[str, Any] | None = None,
    ) -> None:
        """Mark proposal as failed with reason and execution results, and
        revive any Findings that were deferred to this proposal.

        The method performs two sequential operations:

          1. Proposal state UPDATE on core.autonomous_proposals (same
             session, same transaction as the caller's existing context).
          2. Revival of deferred findings via
             BlackboardService.revive_findings_for_failed_proposal.
             Service-owned session/transaction; runs after the proposal
             state commit.

        Eventual consistency, not atomicity — see ADR-010 Layer 3. The
        revival call is idempotent: on a retry it finds the findings
        already 'open' and no-ops, producing a revived_count=0 report.

        Revival failure does not propagate. If the blackboard service
        raises, the proposal is still marked failed (which is the
        load-bearing state transition the caller relies on); the revival
        failure is logged loudly so operators can reconcile manually. This
        matches the non-blocking audit-log pattern elsewhere in the
        codebase (e.g. ActionExecutor._audit_log).
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        # 1. Proposal state transition — caller's session, caller's transaction.
        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(
                status=ProposalStatus.FAILED.value,
                execution_completed_at=datetime.now(UTC),
                failure_reason=reason,
                execution_results=results or {},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.error("Marked proposal as failed: %s - %s", proposal_id, reason)

        # 2. Finding revival — service-owned session, after proposal commit.
        # Implements CORE-Finding.md §7a. If BlackboardService is unavailable
        # or raises, the proposal stays marked failed; revival is logged as
        # unresolved so operators can reconcile.
        try:
            from body.services.service_registry import service_registry

            blackboard_service = await service_registry.get_blackboard_service()
            revival = await blackboard_service.revive_findings_for_failed_proposal(
                proposal_id=proposal_id,
                failure_reason=reason,
            )
            logger.info(
                "Proposal %s failure revival: %d finding(s) revived",
                proposal_id,
                revival["revived_count"],
            )
        except Exception as revival_err:
            logger.error(
                "Non-blocking revival failure for proposal %s: %s. "
                "Proposal remains marked failed. Findings deferred to this "
                "proposal may require manual reconciliation.",
                proposal_id,
                revival_err,
                exc_info=True,
            )

    # -------------------------
    # Approval State Transitions
    # -------------------------

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
