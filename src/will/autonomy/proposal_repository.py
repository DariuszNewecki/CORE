# src/will/autonomy/proposal_repository.py

"""
Proposal Repository - Pure Persistence for A3 Proposals.

CONSTITUTIONAL FIX (V2.3):
- Modularized to reduce Modularity Debt (51.3 -> ~40.0).
- Stripped of state machine logic (delegated to ProposalStateManager).
- Stripped of mapping logic (delegated to ProposalMapper).
- Aligns with the Octopus-UNIX Synthesis: Pure Persistence capability.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from shared.logger import getLogger
from will.autonomy.proposal import Proposal, ProposalStatus
from will.autonomy.proposal_mapper import ProposalMapper


logger = getLogger(__name__)


# ID: 265ff56b-f1a1-45ba-853b-fd4c97d54f72
class ProposalRepository:
    """
    Handles pure CRUD operations for autonomous proposals.

    This is a 'Body' component of the Will layer: it executes
    database instructions but contains no strategic logic.
    """

    def __init__(self, session: Any):
        """
        Initialize with an active database session.

        Constitutional Note: Callers should use the 'open()' context manager
        provided by the service registry.
        """
        self._session = session

    # ID: repo_get
    # ID: f8b8727b-7e4d-4d32-a6cb-475cac9551f7
    async def get(self, proposal_id: str) -> Proposal | None:
        """Retrieves a domain Proposal by its public ID string."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = select(AutonomousProposal).where(
            AutonomousProposal.proposal_id == proposal_id
        )
        result = await self._session.execute(stmt)
        db_record = result.scalar_one_or_none()

        if not db_record:
            return None

        return ProposalMapper.from_db_model(db_record)

    # ID: repo_create
    # ID: 3848ee7d-8eac-4835-abeb-7ea378ae15a5
    async def create(self, proposal: Proposal) -> str:
        """Persists a new proposal record."""
        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        db_model = ProposalMapper.to_db_model(proposal, AutonomousProposal)
        self._session.add(db_model)
        # Flush to get the ID but leave commit to the workflow orchestrator
        await self._session.flush()

        logger.debug("Persisted proposal record: %s", proposal.proposal_id)
        return proposal.proposal_id

    # ID: repo_list_by_status
    # ID: 190fdc4c-77e9-4d99-986b-7c3a0d302560
    async def list_by_status(
        self, status: ProposalStatus, limit: int = 100
    ) -> list[Proposal]:
        """Queries the database for proposals in a specific lifecycle state."""
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

    # ID: repo_update
    # ID: 23d0dc09-c889-41f3-8f11-284e0a894660
    async def update_fields(self, proposal_id: str, updates: dict[str, Any]) -> None:
        """
        Atomic field update.
        Used by StateManager to advance the lifecycle without re-mapping the whole object.
        """
        from sqlalchemy import update

        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            update(AutonomousProposal)
            .where(AutonomousProposal.proposal_id == proposal_id)
            .values(**updates)
        )
        await self._session.execute(stmt)
        # We do not commit here; the Will layer orchestrator manages the transaction.
