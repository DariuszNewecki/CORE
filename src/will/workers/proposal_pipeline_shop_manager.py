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
- Detect proposals whose findings were never deferred to them (the
  creation-side outbox gap, #764) and re-attempt the deferral.
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
                         proposal.stuck_finalizing::<proposal_id>
                         proposal.stuck_undeferred::<proposal_id>
                         proposal.repeated_failure::<action_id>::<rule_id>
- resolution_mechanism:  self_resolve
- Resolver path:         this worker's own run() method, in-Python
                         resolve_entries loop. After the flagging passes,
                         every open proposal.* finding whose subject is
                         NOT in this cycle's flagged_subjects set is
                         resolved via BlackboardService.resolve_entries —
                         the finding clears when the proposal exits its
                         stuck status.
- Not eligible for ADR-045 awaiting_reaudit: proposal pipeline state is
  live runtime state; there is no re-readable artifact for a sensor to
  re-evaluate against.
- ADR-150 exception: a stuck_finalizing finding escalated to the governor
  at the redrive cap (indeterminate/human) is OUTSIDE this resolver's
  reach — the existing-findings fetch is status='open' only, so the
  resolve pass cannot auto-clear an escalation. Its resolver is a human;
  resolving it re-arms detection (ADR-150 D3).

stuck_undeferred redrive contract (#764 — creation-side outbox):
- Originally: create_proposal and defer_entries_to_proposal
  (ViolationRemediatorWorker.run) were separate, independently-committed
  transactions, so a finding could be left at 'claimed' (never reached
  'deferred_to_proposal') — invisible to both revival and re-claim.
  Since #886 the mapped lane creates, defers and (when safe) approves in
  ONE transaction (submit_mapped_proposal), and the test_remediator lane
  has not deferred since #773 T5.3; no live two-step creator remains.
  The redrive is kept as a backstop for a lane that reintroduces the
  two-step shape, not as a path any current lane exercises.
- fetch_stuck_undeferred matches ACTIVE proposals only
  (proposal_status_active: pending/approved/executing/finalizing). A
  terminal proposal's findings are revived by its own failure/rejection
  path and may legitimately be 'open' again — matching those re-deferred
  live findings to a dead proposal every cycle (the #764 mis-fire).
- _redrive_undeferred_findings re-attempts defer_entries_to_proposal
  every cycle the proposal appears in fetch_stuck_undeferred; the
  UPDATE's own status guard (only 'open'/'claimed' rows match) makes
  retries idempotent, and once all findings are deferred the proposal
  stops matching the query, so the finding self-resolves via the
  existing resolve pass.

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
_SUBJECT_STUCK_FINALIZING = "proposal.stuck_finalizing"
_SUBJECT_STUCK_UNDEFERRED = "proposal.stuck_undeferred"
_SUBJECT_STUCK_DEFERRED_TERMINAL = "proposal.stuck_deferred_terminal"
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
        stuck_finalizing = await proposal_svc.fetch_stuck_finalizing(
            sla_sec=_CFG.stuck_finalizing_sla_sec,
            limit=_CFG.findings_scan_limit,
        )
        stuck_undeferred = await proposal_svc.fetch_stuck_undeferred(
            sla_sec=_CFG.stuck_undeferred_sla_sec,
            limit=_CFG.findings_scan_limit,
        )
        stuck_deferred_terminal = await proposal_svc.fetch_stuck_deferred_terminal(
            sla_sec=_CFG.stuck_deferred_terminal_sla_sec,
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
        rolled_forward_proposals = 0
        redriven_proposals = 0
        escalated_proposals = 0
        reconciled_proposals = 0

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

        for row in stuck_finalizing:
            subject = f"{_SUBJECT_STUCK_FINALIZING}::{row['proposal_id']}"
            flagged_subjects.add(subject)

            # Roll the proposal FORWARD every cycle it appears — re-drive the
            # idempotent evidence steps and complete it (ADR-148 D4). Unlike
            # stuck_executing (which retires), a finalizing proposal is already
            # committed; rolling it back would double-apply the change.
            advanced = await self._roll_forward_finalizing(row)
            if advanced:
                rolled_forward_proposals += 1

            entry_id = existing.get(subject)
            if entry_id is None:
                # First detection. The initial count records this cycle's
                # failed redrive (ADR-150 D1); 0 when the roll-forward
                # advanced the proposal (the finding self-resolves next
                # cycle once the proposal leaves the stuck set).
                await self.post_finding(
                    subject=subject,
                    payload={
                        "proposal_id": row["proposal_id"],
                        "execution_completed_at": _isoformat(
                            row["execution_completed_at"]
                        ),
                        "seconds_stuck": row["seconds_stuck"],
                        "sla_seconds": _CFG.stuck_finalizing_sla_sec,
                        "finalization_redrive_count": 0 if advanced else 1,
                    },
                    resolution_mechanism="self_resolve",
                )
                flagged += 1
                logger.warning(
                    "ProposalPipelineShopManager: proposal %s stuck finalizing "
                    "for %ds (sla=%ds) — rolling forward",
                    row["proposal_id"],
                    row["seconds_stuck"],
                    _CFG.stuck_finalizing_sla_sec,
                )
                continue

            if advanced:
                continue

            # ADR-150 D1: count the failed redrive in place on the single
            # persistent open finding — this lifecycle never renews the
            # finding while the proposal stays stuck, so in-place cannot be
            # laundered (contrast ADR-104 D9 counter inheritance, which is
            # for abandoned-and-renewed findings).
            count = await blackboard_svc.increment_finding_counter(
                entry_id, "finalization_redrive_count"
            )
            if count >= _CFG.finalizing_redrive_cap_n:
                # ADR-150 D2: at cap — hand to the governor and stop.
                # indeterminate + human in one statement; the escalated
                # finding drops out of the open-only `existing` fetch (so
                # the resolve pass cannot auto-clear it), and the
                # supervision query's NOT EXISTS guard keeps the proposal
                # out of the redrive set until a human resolves the finding
                # (ADR-150 D3 re-arm).
                escalated = await blackboard_svc.escalate_finding_to_governor(
                    entry_id,
                    {
                        "escalation": "finalizing_redrive_cap_reached",
                        "finalization_redrive_count": count,
                        "cap_n": _CFG.finalizing_redrive_cap_n,
                    },
                )
                if escalated:
                    escalated_proposals += 1
                    logger.error(
                        "ProposalPipelineShopManager: proposal %s exhausted %d "
                        "finalizing redrives — escalated to governor (ADR-150 "
                        "D2); remains finalizing pending human disposition",
                        row["proposal_id"],
                        count,
                    )

        for row in stuck_undeferred:
            subject = f"{_SUBJECT_STUCK_UNDEFERRED}::{row['proposal_id']}"
            flagged_subjects.add(subject)

            # Re-attempt the deferral every cycle the proposal appears
            # (#764). Idempotent: defer_entries_to_proposal's own status
            # guard (WHERE status IN ('open','claimed')) means findings
            # already deferred by a prior partial attempt are left alone.
            redriven = await self._redrive_undeferred_findings(row)
            if redriven:
                redriven_proposals += 1

            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "proposal_id": row["proposal_id"],
                    "finding_ids": row["finding_ids"],
                    "seconds_stuck": row["seconds_stuck"],
                    "sla_seconds": _CFG.stuck_undeferred_sla_sec,
                },
                resolution_mechanism="self_resolve",
            )
            flagged += 1
            logger.warning(
                "ProposalPipelineShopManager: proposal %s has undeferred "
                "findings for %ds (sla=%ds) — redriving",
                row["proposal_id"],
                row["seconds_stuck"],
                _CFG.stuck_undeferred_sla_sec,
            )

        for row in stuck_deferred_terminal:
            subject = f"{_SUBJECT_STUCK_DEFERRED_TERMINAL}::{row['proposal_id']}"
            flagged_subjects.add(subject)

            # Terminate-side twin of the undeferred redrive (#764/#886): the
            # proposal ended but the actor that should have revived (or
            # resolved) its findings never did. Route by the proposal's
            # terminal state through the predicates that already exist —
            # no new destination is decided here. Idempotent: every
            # predicate's WHERE is status-guarded.
            reconciled = await self._reconcile_stuck_deferred_terminal(row)
            if reconciled:
                reconciled_proposals += 1

            if subject in existing:
                continue
            await self.post_finding(
                subject=subject,
                payload={
                    "proposal_id": row["proposal_id"],
                    "proposal_status": row["proposal_status"],
                    "nothing_to_commit": row["nothing_to_commit"],
                    "finding_ids": row["finding_ids"],
                    "seconds_stuck": row["seconds_stuck"],
                    "sla_seconds": _CFG.stuck_deferred_terminal_sla_sec,
                },
                resolution_mechanism="self_resolve",
            )
            flagged += 1
            logger.warning(
                "ProposalPipelineShopManager: %d finding(s) still deferred to "
                "%s proposal %s for %ds (sla=%ds) — reconciling",
                len(row["finding_ids"]),
                row["proposal_status"],
                row["proposal_id"],
                row["seconds_stuck"],
                _CFG.stuck_deferred_terminal_sla_sec,
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
                "stuck_finalizing": len(stuck_finalizing),
                "stuck_undeferred": len(stuck_undeferred),
                "stuck_deferred_terminal": len(stuck_deferred_terminal),
                "repeated_failures": len(repeated_failures),
                "flagged": flagged,
                "resolved": resolved,
                "terminated_proposals": terminated_proposals,
                "rolled_forward_proposals": rolled_forward_proposals,
                "redriven_proposals": redriven_proposals,
                "reconciled_proposals": reconciled_proposals,
                "escalated_proposals": escalated_proposals,
            },
        )
        logger.info(
            "ProposalPipelineShopManager: cycle complete — "
            "stuck_approved=%d stuck_executing=%d stuck_undeferred=%d "
            "stuck_deferred_terminal=%d repeated_failures=%d flagged=%d "
            "resolved=%d terminated=%d redriven=%d reconciled=%d",
            len(stuck_approved),
            len(stuck_executing),
            len(stuck_undeferred),
            len(stuck_deferred_terminal),
            len(repeated_failures),
            flagged,
            resolved,
            terminated_proposals,
            redriven_proposals,
            reconciled_proposals,
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
        from will.autonomy.proposal_consumer_revival import revive_and_report

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
                            WHERE proposal_id = :proposal_id
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

    async def _roll_forward_finalizing(self, row: dict[str, Any]) -> bool:
        """
        Roll a stuck-finalizing proposal FORWARD to completed (ADR-148 D4).

        Re-drives the idempotent finalization steps the executor gates on:
        1. If no consequence record exists, record a best-effort one from the
           persisted proposal data (declared_production recomputed from
           execution_results; the SHAs are unavailable to the reaper and are
           omitted — the git commit already exists, and this record satisfies
           the D1 "consequence chain recorded" obligation). Marked
           consequence_source='reaper_reconstructed' (ADR-148 D7, #790) so
           the row is honestly distinguishable from one captured at
           execution time and surfaced to the governor rather than passing
           silently as equivalent evidence. If a record already exists
           (findings/complete failed but consequence succeeded), it is
           left untouched.
        2. Adjudicate the proposal's deferred findings: resolve them, or —
           when the recorded consequence proves a no-op commit
           (``nothing_to_commit``, ADR-104 D9 / #901) — revive them on the
           capped remediation-attempt path exactly as the executor would
           have, and post that record through this Worker.
        3. mark_completed (finalizing -> completed), status-guarded.

        Fail-soft: any step failing leaves the proposal finalizing and the
        finding open; the next cycle retries. Returns True when this call
        advanced the proposal to completed.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_consumer_revival import report_revival
        from will.autonomy.proposal_execution_pipeline import (
            compute_production_set,
            record_consequence,
            resolve_deferred_findings,
            revive_deferred_findings_for_noop,
        )
        from will.autonomy.proposal_state_manager import (
            ProposalNotFoundError,
            ProposalStateManager,
        )

        proposal_id = row["proposal_id"]
        try:
            if not row.get("has_consequence"):
                declared = compute_production_set(row.get("execution_results") or {})
                consequence_ok = await record_consequence(
                    proposal_id=proposal_id,
                    pre_sha=None,
                    post_sha=None,
                    changed_files=[],
                    finding_ids=list(row.get("finding_ids") or []),
                    policies=list(row.get("policies") or []),
                    declared_production=declared,
                    source="reaper_reconstructed",
                )
                if not consequence_ok:
                    return False

            if row.get("nothing_to_commit"):
                findings_ok, revival = await revive_deferred_findings_for_noop(
                    proposal_id
                )
                if not findings_ok:
                    return False
                if revival:
                    await report_revival(
                        self,
                        proposal_id,
                        revival,
                        report_subject_family="proposal.noop.revival",
                    )
            elif not await resolve_deferred_findings(proposal_id):
                return False

            async with service_registry.session() as session:
                try:
                    await ProposalStateManager(session).mark_completed(proposal_id)
                except ProposalNotFoundError:
                    # Concurrently completed or no longer finalizing — safe no-op.
                    return False

            logger.warning(
                "ProposalPipelineShopManager: rolled forward stuck-finalizing "
                "proposal %s to completed",
                proposal_id,
            )
            return True
        except Exception as roll_err:
            logger.error(
                "ProposalPipelineShopManager: failed to roll forward proposal %s: %s",
                proposal_id,
                roll_err,
            )
            return False

    async def _reconcile_stuck_deferred_terminal(self, row: dict[str, Any]) -> bool:
        """
        Move findings stranded in ``deferred_to_proposal`` on a proposal that
        has already ended to where the proposal's own terminating actor would
        have put them (G4 P2 pre-condition; terminate-side twin of #764/#886).

        Routing, by the proposal's terminal state — every destination is a
        decision already made elsewhere; this method chooses none:

        - ``failed``  → the execution-failure revival (`revive_and_report`,
          lineage-aware, ADR-104 D9 cap; posts the cap observations and the
          revival report through this Worker).
        - ``rejected`` → the governor inbox: ``indeterminate`` + ``human``
          (`revive_ceremony_findings_for_rejected_proposal`; assisted-lane
          rows through their own predicate, same destination). Deliberately
          NOT the live reject routing ``proposal_service.reject`` uses, which
          sends autonomous-lineage findings back to ``awaiting_reaudit`` and
          so to a fresh proposal: this branch runs with no human present,
          weeks after a human said no, and cannot know why (nothing records
          the reason) — re-proposing is the only outcome that can contradict
          a decision already on record, delegating cannot. Same judgment as
          ADR-104 D10 one loop over: ``indeterminate`` + ``human`` where the
          daemon cannot know what should happen. A stranded rejection goes to
          the human; that stays true whatever the live path later learns
          about rejection reasons, because it turns on absent authority.
        - ``completed``, real commit → resolve (`resolve_deferred_findings`).
        - ``completed``, no-op (pre SHA == post SHA) → the ADR-104 D10
          revival (`revive_deferred_findings_for_noop`) + its report.
        - ``missing`` (no proposal row for the deferred id) → as ``failed``:
          the revival predicates key on ``payload.proposal_id`` and do not
          need the proposal row; the dangling id is named in the finding
          this pass posts.

        Fail-soft: any error leaves the findings where they are and the
        next cycle retries. Returns True when a revival/resolution ran.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_consumer_revival import (
            report_revival,
            revive_and_report,
        )
        from will.autonomy.proposal_execution_pipeline import (
            resolve_deferred_findings,
            revive_deferred_findings_for_noop,
        )
        from will.autonomy.proposal_lineage import proposal_lineage

        proposal_id = row.get("proposal_id")
        status = row.get("proposal_status")
        if not proposal_id:
            logger.warning(
                "ProposalPipelineShopManager: %d finding(s) deferred with no "
                "proposal_id in payload — cannot route; left for the governor",
                len(row.get("finding_ids") or []),
            )
            return False
        try:
            if status in ("failed", "missing"):
                await revive_and_report(
                    self,
                    proposal_id,
                    f"stuck_deferred_terminal: proposal {status}, revival never ran",
                )
                return True
            if status == "rejected":
                reason = (
                    "stuck_deferred_terminal: proposal rejected by the governor, "
                    "aftermath never ran — delegated back to the governor"
                )
                bb_service = await service_registry.get_blackboard_service()
                lineage = proposal_lineage(
                    row.get("constitutional_constraints") or None
                )
                if lineage == "assisted_lane":
                    revival = await bb_service.revive_delegated_findings_for_rejected_proposal(
                        proposal_id=proposal_id, reason=reason
                    )
                else:
                    revival = (
                        await bb_service.revive_ceremony_findings_for_rejected_proposal(
                            proposal_id=proposal_id, reason=reason
                        )
                    )
                if revival:
                    await report_revival(
                        self,
                        proposal_id,
                        revival,
                        report_subject_family="proposal.stuck_deferred_terminal.delegated",
                    )
                return True
            if status == "completed":
                if row.get("nothing_to_commit"):
                    ok, revival = await revive_deferred_findings_for_noop(proposal_id)
                    if ok and revival:
                        await report_revival(
                            self,
                            proposal_id,
                            revival,
                            report_subject_family="proposal.noop.revival",
                        )
                    return ok
                return await resolve_deferred_findings(proposal_id)
            logger.warning(
                "ProposalPipelineShopManager: proposal %s in unexpected terminal "
                "state %r — not reconciled",
                proposal_id,
                status,
            )
            return False
        except Exception as rec_err:
            logger.error(
                "ProposalPipelineShopManager: failed to reconcile findings deferred "
                "to %s proposal %s: %s",
                status,
                proposal_id,
                rec_err,
            )
            return False

    async def _redrive_undeferred_findings(self, row: dict[str, Any]) -> bool:
        """
        Re-attempt defer_entries_to_proposal for a proposal's undeferred
        findings (#764 — creation-side outbox).

        Idempotent: defer_entries_to_proposal's own status guard (WHERE
        status IN ('open','claimed')) means findings a prior partial
        attempt already deferred are left untouched — only the genuinely
        stuck ones transition. Returns True if at least one finding was
        deferred by this call.
        """
        from body.services.service_registry import service_registry

        proposal_id = row["proposal_id"]
        finding_ids = row.get("finding_ids") or []
        if not finding_ids:
            return False

        try:
            blackboard_svc = await service_registry.get_blackboard_service()
            deferred_count = await blackboard_svc.defer_entries_to_proposal(
                finding_ids, proposal_id
            )
        except Exception as defer_err:
            logger.error(
                "ProposalPipelineShopManager: failed to redrive undeferred "
                "findings for proposal %s: %s",
                proposal_id,
                defer_err,
            )
            return False

        if deferred_count:
            logger.warning(
                "ProposalPipelineShopManager: redrove %d undeferred finding(s) "
                "for proposal %s",
                deferred_count,
                proposal_id,
            )
        return deferred_count > 0

    async def _fetch_existing_findings(self, blackboard_svc: Any) -> dict[str, str]:
        """
        Return mapping of subject → entry_id for open findings matching
        any of this worker's subject prefixes. Entry_id is needed for the
        resolution pass.
        """
        existing: dict[str, str] = {}
        for prefix in (
            _SUBJECT_STUCK_APPROVED,
            _SUBJECT_STUCK_EXECUTING,
            _SUBJECT_STUCK_FINALIZING,
            _SUBJECT_STUCK_UNDEFERRED,
            _SUBJECT_STUCK_DEFERRED_TERMINAL,
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
