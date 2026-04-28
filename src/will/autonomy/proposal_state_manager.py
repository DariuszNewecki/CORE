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


ALLOWED_APPROVAL_AUTHORITIES: frozenset[str] = frozenset(
    {
        "risk_classification.safe_auto_approval",
        "human.cli_operator",
    }
)
"""Closed set per .intent/META/enums.json proposal_approval_authority.
Mirrored here for write-path validation; .intent/ is the canonical surface."""


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
        """Mark proposal as failed with reason and execution results.

        UPDATE-only: transitions the proposal row on
        core.autonomous_proposals to 'failed' status.

        Revival of deferred findings and posting of the §7a revival report
        are the calling Worker's orchestration responsibility per ADR-011.
        The Worker detects ok=False from ProposalExecutor, invokes the
        blackboard service's revival method (also UPDATE-only), and posts
        the revival report via self.post_report() so the entry carries
        Worker attribution. This method no longer invokes the blackboard
        service directly.
        """
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
                execution_results=results or {},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        logger.error("Marked proposal as failed: %s - %s", proposal_id, reason)

    # -------------------------
    # Approval State Transitions
    # -------------------------

    # ID: befa870d-148c-4f53-9c31-614380e93673
    async def approve(
        self,
        proposal_id: str,
        approved_by: str,
        approval_authority: str,
    ) -> None:
        """Approve proposal for execution.

        approval_authority is non-omittable per URS NFR.5: a proposal cannot
        transition to status='approved' without recording the authority under
        which approval was granted (21 CFR Part 11 §11.50 "meaning of
        signature"; ALCOA+ "Attributable" extends "who" to include role).
        Validation happens at the write path, before any database operation.

        Args:
            proposal_id: Public proposal id.
            approved_by: Identity of the approver (worker tag, operator name).
            approval_authority: Structured reference to the rule or role that
                authorized approval. Must be one of
                ALLOWED_APPROVAL_AUTHORITIES; mirrors the
                proposal_approval_authority enum in .intent/META/enums.json.

        Raises:
            ValueError: If approval_authority is falsy or not in the closed set.
        """
        if not approval_authority:
            raise ValueError(
                "approval_authority is non-omittable per URS NFR.5; "
                "approve() must receive a value from the proposal_approval_authority "
                "closed set."
            )
        if approval_authority not in ALLOWED_APPROVAL_AUTHORITIES:
            raise ValueError(
                f"approval_authority {approval_authority!r} is not in the "
                f"allowed set {sorted(ALLOWED_APPROVAL_AUTHORITIES)!r} "
                "(per .intent/META/enums.json proposal_approval_authority)."
            )

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
                approval_authority=approval_authority,
            )
        )
        await self._session.execute(stmt)
        # Caller controls transactional scope (matches update_fields convention).
        logger.info(
            "Approved proposal: %s by %s under %s",
            proposal_id,
            approved_by,
            approval_authority,
        )

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
