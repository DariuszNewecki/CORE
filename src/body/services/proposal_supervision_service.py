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
                      -- ADR-150 D2: a proposal whose stuck_finalizing finding
                      -- has been escalated to the governor (indeterminate/
                      -- human at the redrive cap) leaves the redrive set until
                      -- a human resolves the finding (D3 re-arm). Keying on
                      -- the escalated finding — not a proposal-row flag —
                      -- makes resolve-the-finding the single re-arm act.
                      AND NOT EXISTS (
                          SELECT 1
                          FROM core.blackboard_entries b
                          WHERE b.entry_type = 'finding'
                            AND b.subject = 'proposal.stuck_finalizing::'
                                            || p.proposal_id::text
                            AND b.status = 'indeterminate'
                      )
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

    # ID: 8a43c113-be31-41c8-a7da-0744b06fe00b
    async def fetch_stuck_undeferred(
        self, sla_sec: int, limit: int
    ) -> list[dict[str, Any]]:
        """
        Return proposals whose declared finding_ids include findings still
        at 'open'/'claimed' (never reached 'deferred_to_proposal') beyond
        the SLA (#764 — creation-side outbox).

        create_proposal and defer_entries_to_proposal are separate,
        independently-committed transactions (ViolationRemediatorWorker.run);
        defer_entries_to_proposal is documented fail-soft — a failure there
        does not reverse proposal creation. A finding stuck at
        'claimed' is invisible to both revival (which matches
        status='deferred_to_proposal') and re-claim (which matches
        status='open'): permanently orphaned without this reconciliation.

        Only proposals with a non-empty finding_ids array are considered;
        forward-only per ADR-015 D7 (historical proposals predating the
        field are not backfilled, so they never match jsonb_typeof=='array'
        with elements).
        """
        from body.services.service_registry import ServiceRegistry

        cutoff = datetime.now(UTC) - timedelta(seconds=sla_sec)

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        p.proposal_id,
                        p.constitutional_constraints->'finding_ids' AS finding_ids,
                        p.created_at,
                        EXTRACT(EPOCH FROM (now() - p.created_at))::int
                            AS seconds_stuck
                    FROM core.autonomous_proposals p
                    WHERE p.status != 'rejected'
                      AND jsonb_typeof(p.constitutional_constraints->'finding_ids')
                          = 'array'
                      AND p.created_at < :cutoff
                      AND EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements_text(
                              p.constitutional_constraints->'finding_ids'
                          ) AS fid
                          JOIN core.blackboard_entries be
                              ON be.id = fid::uuid
                          WHERE be.status IN ('open', 'claimed')
                      )
                    ORDER BY p.created_at ASC
                    LIMIT :limit
                    """
                ),
                {"cutoff": cutoff, "limit": limit},
            )
            rows = result.fetchall()

        return [
            {
                "proposal_id": str(row[0]),
                "finding_ids": list(row[1] or []),
                "created_at": row[2],
                "seconds_stuck": int(row[3]),
            }
            for row in rows
        ]

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
