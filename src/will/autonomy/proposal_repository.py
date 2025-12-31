# src/will/autonomy/proposal_repository.py
# ID: autonomy.proposal_repository
"""
Proposal Repository - Database Operations for A3 Proposals

Handles all proposal CRUD operations with PostgreSQL.
Follows the "database as single source of truth" principle.

ARCHITECTURE:
- All proposals stored in PostgreSQL
- JSONB for flexible structured data
- Indexed for common query patterns
- Transaction-safe operations
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logger import getLogger
from will.autonomy.proposal import Proposal, ProposalStatus


logger = getLogger(__name__)


# ID: proposal_repository
# ID: 265ff56b-f1a1-45ba-853b-fd4c97d54f72
class ProposalRepository:
    """
    Repository for proposal database operations.

    All proposal data flows through this class, ensuring:
    - Consistent database access patterns
    - Transaction safety
    - Query optimization
    - Audit trail integrity
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    # ID: repo_create
    # ID: 2d1bf1f8-d391-45f3-936e-1575c3e06d25
    async def create(self, proposal: Proposal) -> str:
        """
        Create a new proposal in the database.

        Args:
            proposal: Proposal to create

        Returns:
            proposal_id of created proposal
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        # Create model instance directly (don't use to_dict which converts datetimes to strings)
        db_proposal = AutonomousProposal(
            proposal_id=proposal.proposal_id,
            goal=proposal.goal,
            status=proposal.status.value,
            actions=[
                {
                    "action_id": a.action_id,
                    "parameters": a.parameters,
                    "order": a.order,
                }
                for a in proposal.actions
            ],
            scope={
                "files": proposal.scope.files,
                "modules": proposal.scope.modules,
                "symbols": proposal.scope.symbols,
                "policies": proposal.scope.policies,
            },
            risk=(
                {
                    "overall_risk": proposal.risk.overall_risk,
                    "action_risks": proposal.risk.action_risks,
                    "risk_factors": proposal.risk.risk_factors,
                    "mitigation": proposal.risk.mitigation,
                }
                if proposal.risk
                else None
            ),
            created_at=proposal.created_at,  # datetime object, not string!
            created_by=proposal.created_by,
            validation_checks=proposal.validation_checks,
            validation_results=proposal.validation_results,
            execution_started_at=proposal.execution_started_at,
            execution_completed_at=proposal.execution_completed_at,
            execution_results=proposal.execution_results,
            constitutional_constraints=proposal.constitutional_constraints,
            approval_required=proposal.approval_required,
            approved_by=proposal.approved_by,
            approved_at=proposal.approved_at,
            failure_reason=proposal.failure_reason,
        )

        self.session.add(db_proposal)
        await self.session.commit()

        logger.info("Created proposal: %s", proposal.proposal_id)
        return proposal.proposal_id

    # ID: repo_get
    # ID: 14671955-d2a3-4781-bb78-e47afbc77619
    async def get(self, proposal_id: str) -> Proposal | None:
        """
        Get proposal by ID.

        Args:
            proposal_id: Proposal identifier

        Returns:
            Proposal if found, None otherwise
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = select(AutonomousProposal).where(
            AutonomousProposal.proposal_id == proposal_id
        )
        result = await self.session.execute(stmt)
        db_proposal = result.scalar_one_or_none()

        if not db_proposal:
            return None

        # Convert to dataclass
        data = {
            "proposal_id": db_proposal.proposal_id,
            "goal": db_proposal.goal,
            "actions": db_proposal.actions,
            "scope": db_proposal.scope,
            "risk": db_proposal.risk,
            "status": db_proposal.status,
            "created_at": db_proposal.created_at.isoformat(),
            "created_by": db_proposal.created_by,
            "validation_checks": db_proposal.validation_checks,
            "validation_results": db_proposal.validation_results,
            "execution_started_at": (
                db_proposal.execution_started_at.isoformat()
                if db_proposal.execution_started_at
                else None
            ),
            "execution_completed_at": (
                db_proposal.execution_completed_at.isoformat()
                if db_proposal.execution_completed_at
                else None
            ),
            "execution_results": db_proposal.execution_results,
            "constitutional_constraints": db_proposal.constitutional_constraints,
            "approval_required": db_proposal.approval_required,
            "approved_by": db_proposal.approved_by,
            "approved_at": (
                db_proposal.approved_at.isoformat() if db_proposal.approved_at else None
            ),
            "failure_reason": db_proposal.failure_reason,
        }

        return Proposal.from_dict(data)

    # ID: repo_update
    # ID: b0e70e56-6f51-4113-b628-0ff9e193e0dd
    async def update(self, proposal: Proposal) -> None:
        """
        Update existing proposal.

        Args:
            proposal: Proposal with updated data
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        # Get the existing proposal
        stmt = select(AutonomousProposal).where(
            AutonomousProposal.proposal_id == proposal.proposal_id
        )
        result = await self.session.execute(stmt)
        db_proposal = result.scalar_one_or_none()

        if not db_proposal:
            raise ValueError(f"Proposal not found: {proposal.proposal_id}")

        # Update fields
        db_proposal.goal = proposal.goal
        db_proposal.status = proposal.status.value
        db_proposal.actions = [
            {
                "action_id": a.action_id,
                "parameters": a.parameters,
                "order": a.order,
            }
            for a in proposal.actions
        ]
        db_proposal.scope = {
            "files": proposal.scope.files,
            "modules": proposal.scope.modules,
            "symbols": proposal.scope.symbols,
            "policies": proposal.scope.policies,
        }
        db_proposal.risk = (
            {
                "overall_risk": proposal.risk.overall_risk,
                "action_risks": proposal.risk.action_risks,
                "risk_factors": proposal.risk.risk_factors,
                "mitigation": proposal.risk.mitigation,
            }
            if proposal.risk
            else None
        )
        db_proposal.validation_checks = proposal.validation_checks
        db_proposal.validation_results = proposal.validation_results
        db_proposal.execution_started_at = proposal.execution_started_at
        db_proposal.execution_completed_at = proposal.execution_completed_at
        db_proposal.execution_results = proposal.execution_results
        db_proposal.constitutional_constraints = proposal.constitutional_constraints
        db_proposal.approval_required = proposal.approval_required
        db_proposal.approved_by = proposal.approved_by
        db_proposal.approved_at = proposal.approved_at
        db_proposal.failure_reason = proposal.failure_reason

        await self.session.commit()

        logger.info("Updated proposal: %s", proposal.proposal_id)

    # ID: repo_list_by_status
    # ID: 9a87e56c-4cdc-4da4-bf80-703e0a73e3bf
    async def list_by_status(
        self, status: ProposalStatus, limit: int = 100
    ) -> list[Proposal]:
        """
        List proposals with given status.

        Args:
            status: Status to filter by
            limit: Maximum number to return

        Returns:
            List of proposals
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            select(AutonomousProposal)
            .where(AutonomousProposal.status == status.value)
            .order_by(AutonomousProposal.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        db_proposals = result.scalars().all()

        proposals = []
        for db_proposal in db_proposals:
            data = {
                "proposal_id": db_proposal.proposal_id,
                "goal": db_proposal.goal,
                "actions": db_proposal.actions,
                "scope": db_proposal.scope,
                "risk": db_proposal.risk,
                "status": db_proposal.status,
                "created_at": db_proposal.created_at.isoformat(),
                "created_by": db_proposal.created_by,
                "validation_checks": db_proposal.validation_checks,
                "validation_results": db_proposal.validation_results,
                "execution_started_at": (
                    db_proposal.execution_started_at.isoformat()
                    if db_proposal.execution_started_at
                    else None
                ),
                "execution_completed_at": (
                    db_proposal.execution_completed_at.isoformat()
                    if db_proposal.execution_completed_at
                    else None
                ),
                "execution_results": db_proposal.execution_results,
                "constitutional_constraints": db_proposal.constitutional_constraints,
                "approval_required": db_proposal.approval_required,
                "approved_by": db_proposal.approved_by,
                "approved_at": (
                    db_proposal.approved_at.isoformat()
                    if db_proposal.approved_at
                    else None
                ),
                "failure_reason": db_proposal.failure_reason,
            }
            proposals.append(Proposal.from_dict(data))

        return proposals

    # ID: repo_list_pending_approval
    # ID: 8ecd2bcf-6982-4d66-a718-4b8e9a5589d2
    async def list_pending_approval(self, limit: int = 50) -> list[Proposal]:
        """
        List proposals awaiting approval.

        Returns:
            List of proposals needing approval
        """
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            select(AutonomousProposal)
            .where(
                AutonomousProposal.status == ProposalStatus.PENDING.value,
                AutonomousProposal.approval_required,
            )
            .order_by(AutonomousProposal.created_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        db_proposals = result.scalars().all()

        proposals = []
        for db_proposal in db_proposals:
            data = {
                "proposal_id": db_proposal.proposal_id,
                "goal": db_proposal.goal,
                "actions": db_proposal.actions,
                "scope": db_proposal.scope,
                "risk": db_proposal.risk,
                "status": db_proposal.status,
                "created_at": db_proposal.created_at.isoformat(),
                "created_by": db_proposal.created_by,
                "validation_checks": db_proposal.validation_checks,
                "validation_results": db_proposal.validation_results,
                "execution_started_at": (
                    db_proposal.execution_started_at.isoformat()
                    if db_proposal.execution_started_at
                    else None
                ),
                "execution_completed_at": (
                    db_proposal.execution_completed_at.isoformat()
                    if db_proposal.execution_completed_at
                    else None
                ),
                "execution_results": db_proposal.execution_results,
                "constitutional_constraints": db_proposal.constitutional_constraints,
                "approval_required": db_proposal.approval_required,
                "approved_by": db_proposal.approved_by,
                "approved_at": (
                    db_proposal.approved_at.isoformat()
                    if db_proposal.approved_at
                    else None
                ),
                "failure_reason": db_proposal.failure_reason,
            }
            proposals.append(Proposal.from_dict(data))

        return proposals

    # ID: repo_mark_executing
    # ID: 51be5977-1729-407c-9c47-018a565d56c4
    async def mark_executing(self, proposal_id: str) -> None:
        """
        Mark proposal as executing.

        Args:
            proposal_id: Proposal to mark
        """
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
        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("Marked proposal as executing: %s", proposal_id)

    # ID: repo_mark_completed
    # ID: 360b7769-23e8-416d-875b-45e8d3c8194c
    async def mark_completed(self, proposal_id: str, results: dict[str, Any]) -> None:
        """
        Mark proposal as completed.

        Args:
            proposal_id: Proposal to mark
            results: Execution results
        """
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
        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("Marked proposal as completed: %s", proposal_id)

    # ID: repo_mark_failed
    # ID: 2f596c85-0d22-4de4-b919-791346cdb6aa
    async def mark_failed(self, proposal_id: str, reason: str) -> None:
        """
        Mark proposal as failed.

        Args:
            proposal_id: Proposal to mark
            reason: Failure reason
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
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()

        logger.error("Marked proposal as failed: %s - %s", proposal_id, reason)

    # ID: repo_approve
    # ID: befa870d-148c-4f53-9c31-614380e93673
    async def approve(self, proposal_id: str, approved_by: str) -> None:
        """
        Approve a proposal.

        Args:
            proposal_id: Proposal to approve
            approved_by: Who approved it
        """
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
        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("Approved proposal: %s by %s", proposal_id, approved_by)

    # ID: repo_reject
    # ID: dbdfc785-73e1-47c5-a886-3a2435c8dc95
    async def reject(self, proposal_id: str, reason: str) -> None:
        """
        Reject a proposal.

        Args:
            proposal_id: Proposal to reject
            reason: Rejection reason
        """
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
        await self.session.execute(stmt)
        await self.session.commit()

        logger.info("Rejected proposal: %s - %s", proposal_id, reason)
