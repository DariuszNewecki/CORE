# src/will/autonomy/proposal_repository.py

"""
Proposal Repository - Pure CRUD operations for A3 Proposals

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Database CRUD only
- No business logic (validation, state management)
- Session lifecycle via service_registry
- Proper dependency injection

Responsibilities:
1. CRUD operations (create, read, update)
2. Query operations (list_by_status, list_pending_approval)

Extracted to separate modules:
- State transitions → ProposalStateManager
- Domain model conversion → ProposalMapper
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select

from body.services.service_registry import service_registry
from shared.logger import getLogger
from will.autonomy.proposal import Proposal, ProposalStatus
from will.autonomy.proposal_mapper import ProposalMapper


logger = getLogger(__name__)


# ID: proposal_repository
# ID: 265ff56b-f1a1-45ba-853b-fd4c97d54f72
class ProposalRepository:
    """
    Repository for proposal database operations.

    Pure CRUD - no business logic, no state management.

    Usage:
        async with ProposalRepository.open() as repo:
            proposal = await repo.get("id")
            await repo.update(proposal)
    """

    def __init__(self, _session: Any):
        self._session = _session

    # ID: repo_open
    # ID: 8f6d3e46-bfd5-4ec1-8a8e-2f151a9b2e11
    @classmethod
    @asynccontextmanager
    # ID: ffc42bc1-4811-46d1-a7cc-5244de7e6303
    async def open(cls) -> AsyncIterator[ProposalRepository]:
        async with service_registry.session() as session:
            yield cls(session)

    # -------------------------
    # CRUD Operations
    # -------------------------

    # ID: repo_create
    # ID: 2d1bf1f8-d391-45f3-936e-1575c3e06d25
    async def create(self, proposal: Proposal) -> str:
        """Create new proposal in database."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        db_proposal = ProposalMapper.to_db_model(proposal, AutonomousProposal)
        self._session.add(db_proposal)
        await self._session.commit()

        logger.info("Created proposal: %s", proposal.proposal_id)
        return proposal.proposal_id

    # ID: repo_get
    # ID: 14671955-d2a3-4781-bb78-e47afbc77619
    async def get(self, proposal_id: str) -> Proposal | None:
        """Retrieve proposal by ID."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = select(AutonomousProposal).where(
            AutonomousProposal.proposal_id == proposal_id
        )
        result = await self._session.execute(stmt)
        db_proposal = result.scalar_one_or_none()

        if not db_proposal:
            return None

        return ProposalMapper.from_db_model(db_proposal)

    # ID: repo_update
    # ID: b0e70e56-6f51-4113-b628-0ff9e193e0dd
    async def update(self, proposal: Proposal) -> None:
        """Update existing proposal."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = select(AutonomousProposal).where(
            AutonomousProposal.proposal_id == proposal.proposal_id
        )
        result = await self._session.execute(stmt)
        db_proposal = result.scalar_one_or_none()

        if not db_proposal:
            raise ValueError(f"Proposal not found: {proposal.proposal_id}")

        ProposalMapper.update_db_model(db_proposal, proposal)
        await self._session.commit()
        logger.info("Updated proposal: %s", proposal.proposal_id)

    # -------------------------
    # Query Operations
    # -------------------------

    # ID: repo_list_by_status
    # ID: 9a87e56c-4cdc-4da4-bf80-703e0a73e3bf
    async def list_by_status(
        self, status: ProposalStatus, limit: int = 100
    ) -> list[Proposal]:
        """List proposals with given status."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            select(AutonomousProposal)
            .where(AutonomousProposal.status == status.value)
            .order_by(AutonomousProposal.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [ProposalMapper.from_db_model(p) for p in result.scalars().all()]

    # ID: repo_list_pending_approval
    # ID: 8ecd2bcf-6982-4d66-a718-4b8e9a5589d2
    async def list_pending_approval(self, limit: int = 50) -> list[Proposal]:
        """List proposals awaiting approval."""
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
        result = await self._session.execute(stmt)
        return [ProposalMapper.from_db_model(p) for p in result.scalars().all()]
