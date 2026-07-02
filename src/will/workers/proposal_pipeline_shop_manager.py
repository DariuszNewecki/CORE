# src/will/workers/proposal_pipeline_shop_manager.py
"""
ProposalPipelineShopManager - Proposal Pipeline Health Supervisory Worker.

Responsibility (per CORE-ShopManager.md §3.3, issue #170):
- Detect proposals stuck in 'approved' status beyond SLA.
- Detect proposals stuck in 'executing' status beyond SLA — and TERMINATE
  them: transition to 'failed' + revive any deferred findings via the §7a
  revival contract so the remediation-attempt counter accumulates correctly
  (ADR-104 D9 / #637).
- Detect repeated failures for the same (action_id, rule_id) pair
  within the lookback window.
- Post one finding per condition occurrence to the Blackboard, with
  deduplication against already-open findings.
- Resolve open findings whose underlying condition has cleared.

Constitutional standing:
- Declaration:      .intent/workers/proposal_pipeline_shop_manager.yaml
- Class:            acting
- Phase:            audit
- Permitted tools:  none — DB reads + one status-guarded UPDATE
- Approval:         false — termination is autonomous for stuck_executing
- Schedule:         max_interval=300s

ADR-091 D2 Revision B resolution classification:
- Subject prefixes:      proposal.stuck_approved::<proposal_id>
                         proposal.stuck_executing::<proposal_id>
                         proposal.repeated_failure::<action_id>::<rule_id>
- resolution_mechanism:  self_resolve
- Resolver path:         this worker's own run() method, in-Python
                         resolve_entries loop. After the three flagging
                         passes, every open proposal.* finding whose
                         subject is NOT in this cycle's flagged_subjects
                         set is resolved via
                         BlackboardService.resolve_entries — the finding
                         clears when the proposal exits its stuck status.
- Not eligible for ADR-045 awaiting_reaudit: proposal pipeline state is
  live runtime state; there is no re-readable artifact for a sensor to
  re-evaluate against.

stuck_executing termination contract:
- _retire_stuck_proposal runs EVERY cycle the proposal appears in
  fetch_stuck_executing. The UPDATE carries AND status = 'executing',
  so concurrent completion by ProposalConsumerWorker is a safe no-op
  (rowcount=0 → revival skipped). Once termination succeeds the
  proposal exits 'executing'; fetch_stuck_executing won't return it
  next cycle; the finding resolves via the existing resolve pass.
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)

_SUBJECT_STUCK_APPROVED = "proposal.stuck_approved"
_SUBJECT_STUCK_EXECUTING = "proposal.stuck_executing"
_SUBJECT_REPEATED_FAILURE = "proposal.repeated_failure"

_CFG = load_operational_config().workers.proposal_pipeline_shop


# ID: fc948532-8f3a-40d2-991e-a7156a22bb91
class ProposalPipelineShopManager(ScheduledWorker):
    """
    Pipeline health worker: detect pathologies and terminate stuck-executing
    proposals so the remediation-attempt counter accumulates correctly.

    Reads core.autonomous_proposals via ProposalSupervisionService.
    Posts deduplicated findings to the Blackboard for each detected
    condition. Resolves open findings whose underlying condition has
    cleared between cycles.
    """

    declaration_name = "proposal_pipeline_shop_manager"

    def __init__(self) -> None:
        super().__init__()

    # ID: 451a310d-f5eb-48c7-8c23-eea73eb44485
    async def run(self) -> None:
        """
        One supervisory cycle:
        1. Post heartbeat.
        2. Query the three conditions via ProposalSupervisionService.
        3. Terminate stuck-executing proposals (status-guarded) + revive findings.
        4. Post deduplicated findings for each occurrence.
        5. Resolve open findings whose condition has cleared.
        6. Post completion report.
        """
        from body.services.service_registry import service_registry

        await self.post_heartbeat()

        proposal_svc = await service_registry.get_proposal_supervision_service()
        blackboard_svc = await service_registry.get_blackboard_service()

        stuck_approved = await proposal_svc.fetch_stuck_approved(
            sla_sec=_CFG.stuck_approved_sla_sec,
            limit=_CFG.findings_scan_limit,
        )
        stuck_executing = await proposal_svc.fetch_stuck_executing(
            sla_sec=_CFG.stuck_executing_sla_sec,
            limit=_CFG.findings_scan_limit,
        )
        repeated_failures = await proposal_svc.fetch_repeated_failures(
            threshold=_CFG.repeated_failure_threshold,
            lookback_sec=_CFG.repeated_failure_lookback_sec,
            limit=_CFG.findings_scan_limit,
        )

        existing = await self._fetch_existing_findings(blackboard_svc)

        flagged_subjects: set[str] = set()
        flagged = 0
        terminated_proposals = 0

        for row in stuck_approved:
            subject = f"{_SUBJECT_STUCK_APPROVED}::{row['proposal_id']}"
            flagged_subjects.add(subject)
            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "proposal_id": row["proposal_id"],
                    "approved_at": _isoformat(row["approved_at"]),
                    "seconds_stuck": row["seconds_stuck"],
                    "sla_seconds": _CFG.stuck_approved_sla_sec,
                },
                resolution_mechanism="self_resolve",
            )
            flagged += 1
            logger.warning(
                "ProposalPipelineShopManager: proposal %s stuck approved for %ds "
                "(sla=%ds)",
                row["proposal_id"],
                row["seconds_stuck"],
                _CFG.stuck_approved_sla_sec,
            )

        for row in stuck_executing:
            subject = f"{_SUBJECT_STUCK_EXECUTING}::{row['proposal_id']}"
            flagged_subjects.add(subject)

            # Attempt termination + revival every cycle (status-guarded, fail-soft).
            if await self._retire_stuck_proposal(
                row["proposal_id"], row["seconds_stuck"]
            ):
                terminated_proposals += 1

            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "proposal_id": row["proposal_id"],
                    "execution_started_at": _isoformat(row["execution_started_at"]),
                    "seconds_stuck": row["seconds_stuck"],
                    "sla_seconds": _CFG.stuck_executing_sla_sec,
                },
                resolution_mechanism="self_resolve",
            )
            flagged += 1
            logger.warning(
                "ProposalPipelineShopManager: proposal %s stuck executing for %ds "
                "(sla=%ds)",
                row["proposal_id"],
                row["seconds_stuck"],
                _CFG.stuck_executing_sla_sec,
            )

        for row in repeated_failures:
            subject = (
                f"{_SUBJECT_REPEATED_FAILURE}::{row['action_id']}::{row['rule_id']}"
            )
            flagged_subjects.add(subject)
            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "action_id": row["action_id"],
                    "rule_id": row["rule_id"],
                    "failure_count": row["failure_count"],
                    "threshold": _CFG.repeated_failure_threshold,
                    "lookback_seconds": _CFG.repeated_failure_lookback_sec,
                    "last_failure_at": _isoformat(row["last_failure_at"]),
                    "sample_proposal_ids": row["proposal_ids"],
                },
                resolution_mechanism="self_resolve",
            )
            flagged += 1
            logger.warning(
                "ProposalPipelineShopManager: %d failures on (%s, %s) within %ds "
                "(threshold=%d)",
                row["failure_count"],
                row["action_id"],
                row["rule_id"],
                _CFG.repeated_failure_lookback_sec,
                _CFG.repeated_failure_threshold,
            )

        resolved = 0
        for subject, entry_id in existing.items():
            if subject not in flagged_subjects:
                await blackboard_svc.resolve_entries([entry_id])
                resolved += 1
                logger.info(
                    "ProposalPipelineShopManager: %s cleared — resolving open finding",
                    subject,
                )

        await self.post_report(
            subject="proposal_pipeline_shop_manager.run.complete",
            payload={
                "stuck_approved": len(stuck_approved),
                "stuck_executing": len(stuck_executing),
                "repeated_failures": len(repeated_failures),
                "flagged": flagged,
                "resolved": resolved,
                "terminated_proposals": terminated_proposals,
            },
        )
        logger.info(
            "ProposalPipelineShopManager: cycle complete — "
            "stuck_approved=%d stuck_executing=%d repeated_failures=%d "
            "flagged=%d resolved=%d terminated=%d",
            len(stuck_approved),
            len(stuck_executing),
            len(repeated_failures),
            flagged,
            resolved,
            terminated_proposals,
        )

    async def _retire_stuck_proposal(
        self, proposal_id: str, seconds_stuck: int
    ) -> bool:
        """
        Terminate a stuck-executing proposal and revive its deferred findings.

        Issues a status-guarded UPDATE (AND status = 'executing') so that a
        concurrent ProposalConsumerWorker completion is a safe no-op — if the
        proposal transitioned away from 'executing' between fetch_stuck_executing
        and this call, rowcount=0 and revival is skipped.

        Called every cycle the proposal appears in fetch_stuck_executing; retries
        are harmless because the status guard makes the UPDATE idempotent. Once
        termination succeeds the proposal leaves 'executing' and won't appear in
        fetch_stuck_executing next cycle, causing the finding to self-resolve.

        Returns True if this call actually terminated the proposal (rowcount=1),
        False for no-op or error (caller uses this for the cycle counter only).
        """
        from sqlalchemy import text

        from body.services.service_registry import service_registry
        from will.workers.proposal_consumer_revival import revive_and_report

        reason = (
            f"stuck_executing: terminated by ProposalPipelineShopManager "
            f"after {seconds_stuck}s (sla={_CFG.stuck_executing_sla_sec}s)"
        )

        terminated = False
        try:
            async with service_registry.session() as session:
                async with session.begin():
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.autonomous_proposals
                            SET status = 'failed',
                                execution_completed_at = now(),
                                failure_reason = :reason
                            WHERE proposal_id = cast(:proposal_id as uuid)
                              AND status = 'executing'
                            """
                        ),
                        {"proposal_id": proposal_id, "reason": reason},
                    )
                    terminated = result.rowcount > 0
        except Exception as term_err:
            logger.error(
                "ProposalPipelineShopManager: failed to terminate proposal %s: %s",
                proposal_id,
                term_err,
            )
            return False

        if not terminated:
            logger.debug(
                "ProposalPipelineShopManager: proposal %s no longer executing "
                "— skipping revival (already completed or failed)",
                proposal_id,
            )
            return False

        logger.warning(
            "ProposalPipelineShopManager: terminated stuck-executing proposal %s "
            "after %ds",
            proposal_id,
            seconds_stuck,
        )
        await revive_and_report(self, proposal_id, reason)
        return True

    async def _fetch_existing_findings(self, blackboard_svc: Any) -> dict[str, str]:
        """
        Return mapping of subject → entry_id for open findings matching
        any of this worker's three subject prefixes. Entry_id is needed
        for the resolution pass.
        """
        existing: dict[str, str] = {}
        for prefix in (
            _SUBJECT_STUCK_APPROVED,
            _SUBJECT_STUCK_EXECUTING,
            _SUBJECT_REPEATED_FAILURE,
        ):
            rows = await blackboard_svc.fetch_open_findings(
                prefix=f"{prefix}::%",
                limit=_CFG.findings_scan_limit,
            )
            for row in rows:
                existing[row["subject"]] = row["id"]
        return existing


def _isoformat(ts: Any) -> str | None:
    """Format a UTC-aware timestamp for the blackboard payload."""
    if ts is None:
        return None
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)
