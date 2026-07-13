# src/body/services/proposal_supervision_service.py
"""
ProposalSupervisionService - Data-access layer for proposal pipeline health.

Body-layer service exposing the three supervisory queries the
ProposalPipelineShopManager needs against core.autonomous_proposals:

- fetch_stuck_approved:    rows in status='approved' older than SLA
- fetch_stuck_executing:   rows in status='executing' older than SLA
- fetch_repeated_failures: (first action_id, source_check_id) pairs
                           with status='failed' count >= threshold
                           within the lookback window

Constitutional alignment:
- Layer:    body — data-access only, no decisions
- Boundary: no Will imports, no domain reasoning, no LLM
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0e4dacfe-1f57-4978-b30d-94ebea06f862
class ProposalSupervisionService:
    """
    Body layer service. Exposes named methods for the three
    proposal-pipeline-health queries used by ProposalPipelineShopManager.

    All methods open their own session via ServiceRegistry — callers do
    not pass one in. This matches the AuditFindingsService /
    WorkerRegistryService pattern.
    """

    # ID: b9263f77-0a50-4fb1-a845-2e91c7e25eb4
    async def fetch_stuck_approved(
        self, sla_sec: int, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return proposals stuck in status='approved' beyond the SLA.

        Each row carries the proposal_id, approved_at, and seconds_stuck
        so the worker can build a precise finding payload.
        """
        from body.services.service_registry import ServiceRegistry

        cutoff = datetime.now(UTC) - timedelta(seconds=sla_sec)

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        proposal_id,
                        approved_at,
                        EXTRACT(EPOCH FROM (now() - approved_at))::int AS seconds_stuck
                    FROM core.autonomous_proposals
                    WHERE status = 'approved'
                      AND approved_at IS NOT NULL
                      AND approved_at < :cutoff
                    ORDER BY approved_at ASC
                    LIMIT :limit
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": str(row[0]),
                "approved_at": row[1],
                "seconds_stuck": int(row[2]),
            }
            for row in rows
        ]

    # ID: ed19598e-6d0f-431d-897b-e5f69bc4c78a
    async def fetch_stuck_executing(
        self, sla_sec: int, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return proposals stuck in status='executing' beyond the SLA.

        Uses execution_started_at as the anchor (not updated_at — that
        moves on any UPDATE and would hide a genuinely stuck row).
        """
        from body.services.service_registry import ServiceRegistry

        cutoff = datetime.now(UTC) - timedelta(seconds=sla_sec)

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        proposal_id,
                        execution_started_at,
                        EXTRACT(EPOCH FROM (now() - execution_started_at))::int
                            AS seconds_stuck
                    FROM core.autonomous_proposals
                    WHERE status = 'executing'
                      AND execution_started_at IS NOT NULL
                      AND execution_started_at < :cutoff
                    ORDER BY execution_started_at ASC
                    LIMIT :limit
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": str(row[0]),
                "execution_started_at": row[1],
                "seconds_stuck": int(row[2]),
            }
            for row in rows
        ]

    # ID: 93bff99e-f795-451b-a2ed-c1c2133df60e
    async def fetch_stuck_finalizing(
        self, sla_sec: int, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return proposals stuck in status='finalizing' beyond the SLA, with the
        data needed to roll them FORWARD (ADR-148 D4).

        Anchored on execution_completed_at (set when the proposal entered
        finalizing) — not updated_at. Includes execution_results (to recompute
        the declared production set), finding_ids and policies (to record the
        consequence), and whether a consequence record already exists, so the
        reaper can complete the finalization idempotently without the executor's
        original SHA context.
        """
        from body.services.service_registry import ServiceRegistry

        cutoff = datetime.now(UTC) - timedelta(seconds=sla_sec)

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        p.proposal_id,
                        p.execution_completed_at,
                        EXTRACT(EPOCH FROM (now() - p.execution_completed_at))::int
                            AS seconds_stuck,
                        p.execution_results,
                        p.constitutional_constraints->'finding_ids' AS finding_ids,
                        p.scope->'policies' AS policies,
                        (c.proposal_id IS NOT NULL) AS has_consequence
                    FROM core.autonomous_proposals p
                    LEFT JOIN core.proposal_consequences c
                        ON c.proposal_id = p.proposal_id
                    WHERE p.status = 'finalizing'
                      AND p.execution_completed_at IS NOT NULL
                      AND p.execution_completed_at < :cutoff
                    ORDER BY p.execution_completed_at ASC
                    LIMIT :limit
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": str(row[0]),
                "execution_completed_at": row[1],
                "seconds_stuck": int(row[2]),
                "execution_results": row[3] or {},
                "finding_ids": row[4] or [],
                "policies": row[5] or [],
                "has_consequence": bool(row[6]),
            }
            for row in rows
        ]

    # ID: 3f325bf4-3f14-4b15-bcfa-17a64f8c56db
    async def fetch_repeated_failures(
        self,
        threshold: int,
        lookback_sec: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Return (action_id, rule_id) pairs whose proposals have failed
        at least *threshold* times within the lookback window.

        Action_id is read from actions[0]->>'action_id' — the first
        action of the proposal, by design decision (the secondary-
        action variant is deferred; see #170 design notes).

        Rule_id is read from constitutional_constraints->>'source_check_id',
        the conventional key for the audit rule that triggered the
        autonomous proposal.
        """
        from body.services.service_registry import ServiceRegistry

        since = datetime.now(UTC) - timedelta(seconds=lookback_sec)

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        actions->0->>'action_id'                          AS action_id,
                        constitutional_constraints->>'source_check_id'    AS rule_id,
                        COUNT(*)                                          AS failure_count,
                        MAX(updated_at)                                   AS last_failure_at,
                        array_agg(proposal_id ORDER BY updated_at DESC)   AS proposal_ids
                    FROM core.autonomous_proposals
                    WHERE status = 'failed'
                      AND updated_at >= :since
                      AND actions->0->>'action_id' IS NOT NULL
                      AND constitutional_constraints->>'source_check_id' IS NOT NULL
                    GROUP BY action_id, rule_id
                    HAVING COUNT(*) >= :threshold
                    ORDER BY failure_count DESC, last_failure_at DESC
                    LIMIT :limit
                    """
                ),
                {"since": since, "threshold": threshold, "limit": limit},
            )
            rows = result.fetchall()

        return [
            {
                "action_id": str(row[0]),
                "rule_id": str(row[1]),
                "failure_count": int(row[2]),
                "last_failure_at": row[3],
                "proposal_ids": [str(p) for p in (row[4] or [])][:5],
            }
            for row in rows
        ]

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
                        proposal_id,
                        execution_completed_at,
                        updated_at
                    FROM core.autonomous_proposals
                    WHERE status = 'completed'
                      AND consequence_recorded_at IS NULL
                      AND execution_completed_at >= :barrier_live_at
                    ORDER BY updated_at DESC
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
