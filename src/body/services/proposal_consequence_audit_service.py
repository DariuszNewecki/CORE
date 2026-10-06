# src/body/services/proposal_consequence_audit_service.py
"""
ProposalConsequenceAuditService - Data-access layer for ADR-148 consequence
integrity.

Body-layer service exposing the two consequence-integrity queries the
CommitAuthorshipAuditWorker needs against core.autonomous_proposals /
core.proposal_consequences:

- fetch_completed_without_consequence:        completed proposals lacking a
                                              durable consequence row (D5)
- fetch_completed_with_degraded_consequence:  completed proposals whose
                                              consequence row was
                                              reaper-reconstructed (D7)

Split from ProposalSupervisionService (ADR-095, modularity.class_too_large):
that service keeps the pipeline-health reads used by
ProposalPipelineShopManager; these audit reads serve a different consumer.

Constitutional alignment:
- Layer:    body — data-access only, no decisions
- Boundary: no Will imports, no domain reasoning, no LLM
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: b1198991-cb9c-4cde-939d-5eeba6a6c49b
class ProposalConsequenceAuditService:
    """
    Body layer service. Exposes named methods for the ADR-148 D5/D7
    consequence-integrity queries used by CommitAuthorshipAuditWorker.

    All methods open their own session via ServiceRegistry — callers do
    not pass one in. This matches the ProposalSupervisionService /
    WorkerRegistryService pattern.
    """

    # ADR-148's consequence_recorded_at column has no backfill (migration
    # 20260712_adr148_finalizing_and_consequence_recorded_at.sql, applied
    # 2026-07-12 20:25:34 UTC) — every row completed before this instant is
    # NULL regardless of legitimacy; the finalization barrier didn't exist
    # yet to set it. Same grandfather-clause shape as this table's own
    # approval_authority_required_when_approved CHECK (created_at <
    # '2026-04-27'). Without this cutoff fetch_completed_without_consequence
    # would flag every pre-ADR-148 completed proposal as a violation.
    _ADR_148_BARRIER_LIVE_AT = datetime(2026, 7, 12, 20, 25, 34, tzinfo=UTC)

    # ID: c020638a-5208-476f-bb7f-7257051a31b3
    async def fetch_completed_without_consequence(
        self, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return proposals in status='completed' lacking a durable consequence
        record (ADR-148 D5), completed after the finalization barrier existed.

        Checks for the actual absence of a core.proposal_consequences row via
        NOT EXISTS, not merely a null consequence_recorded_at marker (#789):
        the marker and the row are written together by every known path
        today, but a query that only inspects the marker would pass even if
        a future bug set the timestamp without writing the row — exactly the
        drift this audit exists to catch. NOT EXISTS makes the row itself
        the ground truth.

        By construction, both the executor's finalizing->completed transition
        (D2) and ProposalPipelineShopManager's stuck_finalizing roll-forward
        (D4) record the consequence before marking completed — a row matching
        this query indicates that invariant was violated (bug or race), not
        a pre-ADR-148 row completed before the barrier existed (those are
        excluded via _ADR_148_BARRIER_LIVE_AT).
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        p.proposal_id,
                        p.execution_completed_at,
                        p.updated_at
                    FROM core.autonomous_proposals p
                    WHERE p.status = 'completed'
                      AND p.execution_completed_at >= :barrier_live_at
                      AND NOT EXISTS (
                          SELECT 1 FROM core.proposal_consequences pc
                          WHERE pc.proposal_id = p.proposal_id
                      )
                    ORDER BY p.updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit, "barrier_live_at": self._ADR_148_BARRIER_LIVE_AT},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": str(row[0]),
                "execution_completed_at": row[1],
                "updated_at": row[2],
            }
            for row in rows
        ]

    # ID: 3ce76e75-b2fb-4ea0-b7ea-8af3ebddef39
    async def fetch_completed_with_degraded_consequence(
        self, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return proposals in status='completed' whose consequence record was
        synthesized by the stuck_finalizing roll-forward rather than
        captured at execution time (ADR-148 D7, #790).

        Selects strictly on consequence_source = 'reaper_reconstructed' —
        never on SHA nullness, since capture_git_sha() already returns None
        fail-soft on the normal execution path (pre_execution_sha IS NULL
        alone cannot distinguish "reconstructed" from "normal execution,
        git capture legitimately failed"). Unlike its sibling
        fetch_completed_without_consequence, this query needs no
        _ADR_148_BARRIER_LIVE_AT exclusion: 'reaper_reconstructed' is a
        value only this ADR's code ever writes, so no pre-barrier row can
        carry it — the predicate is self-limiting to the post-barrier world.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        p.proposal_id,
                        p.execution_completed_at,
                        p.updated_at
                    FROM core.autonomous_proposals p
                    JOIN core.proposal_consequences pc
                        ON pc.proposal_id = p.proposal_id
                    WHERE p.status = 'completed'
                      AND pc.consequence_source = 'reaper_reconstructed'
                    ORDER BY p.updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": str(row[0]),
                "execution_completed_at": row[1],
                "updated_at": row[2],
            }
            for row in rows
        ]
