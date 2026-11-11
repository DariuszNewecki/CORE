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

from collections.abc import Iterable
from typing import Any

from sqlalchemy import or_, select

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.pagination import decode_cursor, encode_cursor
from will.autonomy.proposal import Proposal, ProposalStatus
from will.autonomy.proposal_mapper import ProposalMapper


logger = getLogger(__name__)

_CFG_PR = load_operational_config().proposals


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

    # ID: 190fdc4c-77e9-4d99-986b-7c3a0d302560
    async def list_by_status(
        self, status: ProposalStatus, limit: int = _CFG_PR.list_limit
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
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        return [ProposalMapper.from_db_model(p) for p in result.scalars().all()]

    # ID: 6f0b2c1e-8d4a-4b7e-9c3f-2a5d1e7b9c40
    async def flow_targets(
        self,
        flow_id: str,
        statuses: Iterable[ProposalStatus],
        param_keys: tuple[str, str],
    ) -> set[tuple[str, str]]:
        """Every (param_a, param_b) pair named by an action of ``flow_id`` in a
        proposal whose status is in ``statuses``.

        No row limit and no row lock: a dedup check must see every proposal in
        flight. ``list_by_status`` returns only the newest ``list_limit`` rows
        and skips locked ones, so a caller that dedups on it misses the rest.
        """
        from sqlalchemy import column, func, true
        from sqlalchemy.dialects.postgresql import JSONB

        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        action = func.jsonb_array_elements(AutonomousProposal.actions).table_valued(
            column("value", JSONB)
        )
        value = action.c.value
        key_a, key_b = param_keys
        param_a = value["parameters"][key_a].astext
        param_b = value["parameters"][key_b].astext
        stmt = (
            select(param_a, param_b)
            .select_from(AutonomousProposal)
            .join(action, true())
            .where(AutonomousProposal.status.in_([s.value for s in statuses]))
            .where(value["flow_id"].astext == flow_id)
            .where(param_a.is_not(None))
            .where(param_b.is_not(None))
            .distinct()
        )
        result = await self._session.execute(stmt)
        return {(a, b) for a, b in result.all()}

    # ID: 1e309abf-d835-4f39-a9d9-03d9eedf4474
    async def list_by_status_paginated(
        self,
        status: ProposalStatus,
        limit: int,
        after_cursor: str | None = None,
    ) -> tuple[list[Proposal], bool, str | None]:
        """Keyset-paginated list of proposals in a given status.

        Returns (proposals, has_more, next_cursor). Callers pass next_cursor
        as `after` on the next request to advance the page.
        """
        from sqlalchemy import and_

        from shared.infrastructure.database.models.autonomous_proposals import (
            AutonomousProposal,
        )

        stmt = (
            select(AutonomousProposal)
            .where(AutonomousProposal.status == status.value)
            .order_by(
                AutonomousProposal.created_at.desc(),
                AutonomousProposal.proposal_id.desc(),
            )
            .limit(limit + 1)
            .with_for_update(skip_locked=True)
        )

        if after_cursor is not None:
            cursor_at, cursor_key = decode_cursor(after_cursor)
            if cursor_at is not None:
                stmt = stmt.where(
                    or_(
                        AutonomousProposal.created_at < cursor_at,
                        and_(
                            AutonomousProposal.created_at == cursor_at,
                            AutonomousProposal.proposal_id < cursor_key,
                        ),
                    )
                )

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor: str | None = None
        if has_more and page:
            last = page[-1]
            next_cursor = encode_cursor(last.created_at, last.proposal_id)
        return [ProposalMapper.from_db_model(p) for p in page], has_more, next_cursor

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
