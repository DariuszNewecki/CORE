# src/will/autonomy/proposal_service.py

"""
Proposal Service - High-Level Facade

CONSTITUTIONAL ALIGNMENT:
- Facade Pattern: Simplifies common workflows
- Coordinates Repository + StateManager
- Provides convenience methods for callers

This is the primary entry point for proposal operations.
Use this instead of accessing Repository/StateManager directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text

from body.services.service_registry import service_registry
from shared.logger import getLogger
from will.autonomy.proposal import Proposal, ProposalScope, ProposalStatus
from will.autonomy.proposal_repository import ProposalRepository
from will.autonomy.proposal_state_manager import ProposalStateManager


logger = getLogger(__name__)


# ID: 1f2e3d4c-5b6a-7890-1234-567890abcdef
class ProposalService:
    """
    High-level service for proposal operations.

    Coordinates CRUD (repository) and state management (state manager).

    Usage:
        async with ProposalService.open() as service:
            proposal = await service.get("id")
            await service.mark_executing("id")
    """

    def __init__(self, session: Any):
        self._session = session
        self._repository = ProposalRepository(session)
        self._state_manager = ProposalStateManager(session)

    @classmethod
    @asynccontextmanager
    # ID: 1c11271b-7170-4a70-93d3-25afeb7701c6
    async def open(cls) -> AsyncIterator[ProposalService]:
        """Open service with managed session."""
        async with service_registry.session() as session:
            yield cls(session)

    # -------------------------
    # CRUD Operations (delegate to repository)
    # -------------------------

    # ID: 4b27f951-a174-4623-ba8b-6ca021b74e5e
    async def create(self, proposal: Proposal) -> str:
        """Create new proposal."""
        return await self._repository.create(proposal)

    # ID: 6ffa51f0-c7bd-4ea8-bd18-5cd79c76b6f1
    async def get(self, proposal_id: str) -> Proposal | None:
        """Get proposal by ID."""
        return await self._repository.get(proposal_id)

    # ID: a576c452-efd2-466a-a296-44af1bbd0015
    async def update(self, proposal: Proposal) -> None:
        """Update proposal."""
        await self._repository.update(proposal)

    # ID: 03c9360e-4bae-4a75-b208-8fe1c0c1d58b
    async def list_by_status(
        self, status: ProposalStatus, limit: int = 100
    ) -> list[Proposal]:
        """List proposals by status."""
        return await self._repository.list_by_status(status, limit)

    # ID: f046639e-4ca6-4d4c-9068-e5d27bdd9857
    async def list_pending_approval(self, limit: int = 50) -> list[Proposal]:
        """List proposals awaiting approval."""
        return await self._repository.list_pending_approval(limit)

    # -------------------------
    # State Transitions (delegate to state manager)
    # -------------------------

    # ID: 01f23465-3c5e-43b9-94b3-8634e449be6a
    async def mark_executing(self, proposal_id: str) -> None:
        """Mark proposal as executing."""
        await self._state_manager.mark_executing(proposal_id)

    # ID: bc89da1a-1a65-4982-8e45-1e85d5bea7c6
    async def mark_completed(self, proposal_id: str, results: dict[str, Any]) -> None:
        """Mark proposal as completed."""
        await self._state_manager.mark_completed(proposal_id, results)

    # ID: c30a8f14-0c38-4c1b-b42b-675d5e498ca7
    async def mark_failed(self, proposal_id: str, reason: str) -> None:
        """Mark proposal as failed."""
        await self._state_manager.mark_failed(proposal_id, reason)

    # ID: b2d228b9-fe0a-436a-9fec-1d4f590e337e
    async def approve(
        self,
        proposal_id: str,
        approved_by: str,
        approval_authority: str,
    ) -> None:
        """Approve proposal.

        approval_authority is non-omittable per URS NFR.5; forwarded to
        ProposalStateManager.approve which validates against the
        proposal_approval_authority closed set.

        Commits the session after the state-manager call, since
        ProposalStateManager.approve no longer commits internally.
        """
        await self._state_manager.approve(proposal_id, approved_by, approval_authority)
        await self._session.commit()

    # ID: ca316432-a09e-4af3-9a63-82a39b08ebb2
    async def reject(self, proposal_id: str, reason: str) -> None:
        """Reject proposal."""
        await self._state_manager.reject(proposal_id, reason)

    # -------------------------
    # Convenience Methods
    # -------------------------

    # ID: bdd4ca3b-32e5-46ae-bf1b-c3b1cbb96776
    async def get_or_fail(self, proposal_id: str) -> Proposal:
        """
        Get proposal or raise error if not found.

        Raises:
            ValueError: If proposal doesn't exist
        """
        proposal = await self.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")
        return proposal

    # ID: a2a541cc-520e-4795-a406-c9caf7806a25
    async def execute_workflow(
        self, proposal_id: str, executor_func: Any
    ) -> dict[str, Any]:
        """
        Execute full workflow with state tracking.

        Args:
            proposal_id: Proposal to execute
            executor_func: Async function that executes actions

        Returns:
            Execution results
        """
        await self.mark_executing(proposal_id)
        try:
            results = await executor_func()
            await self.mark_completed(proposal_id, results)
            return results
        except Exception as e:
            await self.mark_failed(proposal_id, str(e))
            raise

    # -------------------------
    # Blast Radius / Scope
    # -------------------------

    # ID: 3e4f5a6b-7c8d-9e0f-1a2b-3c4d5e6f7a8b
    async def populate_scope_from_blast_radius(
        self,
        proposal: Proposal,
        target_symbol_paths: list[str],
    ) -> ProposalScope:
        """
        Query v_symbol_blast_radius for the given symbols and return a
        fully-populated ProposalScope.

        The scope aggregates across all target symbols:
          - symbols: the target symbols themselves + all transitively affected symbols
          - files:   all distinct file_paths in the blast radius
          - modules: all distinct module dotted paths in the blast radius

        Args:
            proposal: The proposal being built (not mutated here — caller assigns scope).
            target_symbol_paths: List of symbol_path values to analyse
                                 (e.g. ["src/will/autonomy/proposal_service.py::ProposalService.create"])

        Returns:
            A ProposalScope populated from the blast radius data.
        """
        if not target_symbol_paths:
            logger.warning(
                "populate_scope_from_blast_radius called with empty target list "
                "for proposal '%s'",
                getattr(proposal, "proposal_id", "?"),
            )
            return ProposalScope()

        result = await self._session.execute(
            text(
                """
                SELECT
                    v.symbol_path,
                    v.file_path,
                    v.module,
                    v.affected_files,
                    v.affected_modules,
                    v.affected_symbol_count
                FROM core.v_symbol_blast_radius v
                WHERE v.symbol_path = ANY(:paths)
                """
            ),
            {"paths": list(target_symbol_paths)},
        )
        rows = result.fetchall()

        if not rows:
            logger.warning(
                "populate_scope_from_blast_radius: none of %d target symbol(s) "
                "found in v_symbol_blast_radius",
                len(target_symbol_paths),
            )
            return ProposalScope(symbols=list(target_symbol_paths))

        all_symbols: set[str] = set(target_symbol_paths)
        all_files: set[str] = set()
        all_modules: set[str] = set()

        for row in rows:
            # Own file and module
            if row.file_path:
                all_files.add(row.file_path)
            if row.module:
                all_modules.add(row.module)

            # Blast radius aggregates (arrays may be None when no callers exist)
            for fp in row.affected_files or []:
                if fp:
                    all_files.add(fp)
            for mod in row.affected_modules or []:
                if mod:
                    all_modules.add(mod)

        logger.info(
            "populate_scope_from_blast_radius: %d target(s) → %d file(s), "
            "%d module(s) in scope",
            len(rows),
            len(all_files),
            len(all_modules),
        )

        return ProposalScope(
            symbols=sorted(all_symbols),
            files=sorted(all_files),
            modules=sorted(all_modules),
        )
