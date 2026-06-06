# src/will/workers/proposal_pipeline_shop_manager.py
"""
ProposalPipelineShopManager - Proposal Pipeline Health Supervisory Worker.

Responsibility (per CORE-ShopManager.md §3.3, issue #170):
- Detect proposals stuck in 'approved' status beyond SLA.
- Detect proposals stuck in 'executing' status beyond SLA.
- Detect repeated failures for the same (action_id, rule_id) pair
  within the lookback window.
- Post one finding per condition occurrence to the Blackboard, with
  deduplication against already-open findings.
- Resolve open findings whose underlying condition has cleared.

Constitutional standing:
- Declaration:      .intent/workers/proposal_pipeline_shop_manager.yaml
- Class:            supervision
- Phase:            audit
- Permitted tools:  none — deterministic DB reads only
- Approval:         false — findings are observations only
- Schedule:         max_interval=300s

Out of scope: recovery / unstick logic for the *proposal itself*. The
worker does not advance, retry, or terminate stuck/failed proposals —
that's the operator's responsibility. The worker DOES however own the
open → resolved transition of its OWN findings; see the resolution
classification block below.

LAYER: will/workers — supervisory worker. Reads core.autonomous_proposals
via the body-layer ProposalSupervisionService. Writes findings to
Blackboard via the Worker base class. No LLM. No file writes.

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
                         clears when the proposal exits its stuck status
                         (operator unstuck, retry, terminate) or the
                         repeated-failure window slides past the
                         threshold. The "out of scope" line above refers
                         to recovery of the *proposal*, not closure of
                         the *finding* this worker posted — the latter
                         is in scope per Revision B (d).
- Not eligible for ADR-045 awaiting_reaudit: proposal pipeline state is
  live runtime state; there is no re-readable artifact for a sensor to
  re-evaluate against.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SUBJECT_STUCK_APPROVED = "proposal.stuck_approved"
_SUBJECT_STUCK_EXECUTING = "proposal.stuck_executing"
_SUBJECT_REPEATED_FAILURE = "proposal.repeated_failure"

_CFG = load_operational_config().workers.proposal_pipeline_shop


# ID: fc948532-8f3a-40d2-991e-a7156a22bb91
class ProposalPipelineShopManager(Worker):
    """
    Supervisory worker for proposal pipeline health.

    Reads core.autonomous_proposals via ProposalSupervisionService.
    Posts deduplicated findings to the Blackboard for each detected
    condition. Resolves open findings whose underlying condition has
    cleared between cycles.
    """

    declaration_name = "proposal_pipeline_shop_manager"

    def __init__(self) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 300)

    # ID: 4312be9a-df25-4fc2-b19e-2cc8eb413d26
    async def run_loop(self) -> None:
        """Continuous self-scheduling loop. Started once by the daemon."""
        logger.info(
            "ProposalPipelineShopManager: starting loop (max_interval=%ds)",
            self._max_interval,
        )
        await self._register()

        while True:
            cycle_start = time.monotonic()
            try:
                await self.run()
            except Exception as exc:
                logger.error(
                    "ProposalPipelineShopManager: cycle failed: %s",
                    exc,
                    exc_info=True,
                )
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="proposal_pipeline_shop_manager.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception(
                        "ProposalPipelineShopManager: failed to post error report"
                    )

            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(self._max_interval - elapsed, 0))

    # ID: 451a310d-f5eb-48c7-8c23-eea73eb44485
    async def run(self) -> None:
        """
        One supervisory cycle:
        1. Post heartbeat.
        2. Query the three conditions via ProposalSupervisionService.
        3. Post deduplicated findings for each occurrence.
        4. Resolve open findings whose condition has cleared.
        5. Post completion report.
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
            },
        )
        logger.info(
            "ProposalPipelineShopManager: cycle complete — "
            "stuck_approved=%d stuck_executing=%d repeated_failures=%d "
            "flagged=%d resolved=%d",
            len(stuck_approved),
            len(stuck_executing),
            len(repeated_failures),
            flagged,
            resolved,
        )

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
