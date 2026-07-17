# src/will/workers/commit_authorship_audit_worker.py
"""
CommitAuthorshipAuditWorker — ADR-129 D4 authorship integrity sensor,
extended with ADR-148 D5 finalization integrity.

Two independent audits share this worker's cadence and blackboard-posting
pattern (same service-registry access, same dedup-by-open-subject shape):

1. Authorship integrity (ADR-129 D4, original). For each autonomous commit
   in the recent consequence log, verifies that the actual git diff
   (files_changed between pre- and post-execution SHAs) is a subset of the
   declared production set (declared_production). Any path in the diff that
   is NOT in declared_production indicates staging contamination: bytes
   from a concurrent session were swept into the autonomous commit,
   violating ADR-101 D1. Posts
   governance.commit_authorship_integrity::{proposal_id}.

2. Finalization integrity (ADR-148 D5, added 2026-07-13). A proposal in
   status='completed' without a durable consequence record violates the
   D2/D4 invariant that consequence_recorded_at is always set before
   mark_completed. Posts
   governance.proposal_finalization_integrity::{proposal_id}.

3. Consequence evidence degraded (ADR-148 D7, added 2026-07-17, #790). A
   proposal in status='completed' whose consequence row exists but was
   synthesized by ProposalPipelineShopManager's stuck_finalizing
   roll-forward (consequence_source='reaper_reconstructed') satisfies check
   2 above (the row is present) but carries fabricated, empty evidence —
   pre/post SHA and files_changed are empty by construction, not by
   observation. Posts
   governance.consequence_evidence_degraded::{proposal_id}.

All three are 'reporting' posture, no auto-remediation — detection only, per
ADR-129 D5 / ADR-148 D5's stated ramp (reporting -> resolve drift -> blocking).

Constitutional standing:
- Declaration: .intent/workers/commit_authorship_audit_worker.yaml
- Class: governance
- Phase: audit
- Permitted tools: none (no LLM calls)
- Approval: false

DB access via Body service registry only (Will pattern per ADR-019 D1).
Git diff via GitService.diff_file_names (shared sanctuary; no direct
subprocess in Will per governance.dangerous_execution_primitives).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: d293f6d4-1a2b-4c3d-8e5f-6a7b8c9d0e1f
class CommitAuthorshipAuditWorker(Worker):
    """
    Governance worker running two independent post-hoc integrity audits.

    Authorship (ADR-129 D4): compares declared_production (what commit_paths
    was authorized to commit) against the actual git diff (what was
    committed) for each autonomous proposal in the last 7 days. Detects
    staging contamination introduced by the pre-ADR-129-D1 gap in
    commit_paths.

    Rows written before ADR-129 was deployed have declared_production = []
    (the column default). The worker skips those rows as unverifiable —
    it cannot reconstruct what the action declared at the time, so treating
    them as violations would produce false positives. Coverage begins from
    the first proposal executed after the declared_production column was
    populated (after migration 20260628_adr129_add_declared_production_
    to_proposal_consequences.sql was applied).

    Finalization integrity (ADR-148 D5, added 2026-07-13): flags any
    status='completed' proposal missing consequence_recorded_at. Rows
    completed before the ADR-148 barrier existed are excluded via
    ProposalSupervisionService._ADR_148_BARRIER_LIVE_AT — same
    unverifiable-history exclusion shape as the authorship audit above.

    Consequence evidence degraded (ADR-148 D7, added 2026-07-17, #790):
    flags any status='completed' proposal whose consequence row has
    consequence_source='reaper_reconstructed' — present, but fabricated.
    No barrier-date exclusion needed: that value is only ever written by
    this ADR's own code, so no pre-barrier row can carry it.

    Runs hourly (schedule.max_interval: 3600 in YAML). Deduplicates
    against open blackboard findings to avoid re-posting on each cycle.
    """

    declaration_name = "commit_authorship_audit_worker"

    def __init__(self, core_context: Any) -> None:
        super().__init__()
        self._core_context = core_context

    # ID: c4780228-9f0e-4d5a-b6c7-8d9e0f1a2b3c
    async def run(self) -> None:
        """Audit recent autonomous commits for authorship integrity violations."""
        await self.post_heartbeat()

        from body.services.service_registry import service_registry

        blackboard_service = await service_registry.get_blackboard_service()
        existing = await blackboard_service.fetch_active_finding_subjects_by_prefix(
            "governance.commit_authorship_integrity::%"
        )

        consequence_svc = (
            await self._core_context.registry.get_consequence_log_service()
        )
        entries = await consequence_svc.get_recent_for_audit(lookback_days=7)

        git_service = self._core_context.git_service

        checked = 0
        skipped_no_declared = 0
        violations = 0
        suppressed = 0

        for entry in entries:
            proposal_id = entry["proposal_id"]
            pre_sha = entry["pre_execution_sha"]
            post_sha = entry["post_execution_sha"]
            declared = set(entry["declared_production"])

            # Pre-ADR-129 rows have empty declared_production — unverifiable.
            if not declared:
                skipped_no_declared += 1
                continue

            if not pre_sha:
                skipped_no_declared += 1
                continue

            checked += 1
            actual_diff = await git_service.diff_file_names(pre_sha, post_sha)
            if actual_diff is None:
                # git failure — don't post a false positive, just skip.
                continue

            extra = set(actual_diff) - declared
            if not extra:
                continue

            violations += 1
            subject = f"governance.commit_authorship_integrity::{proposal_id}"
            if subject in existing:
                suppressed += 1
                logger.debug(
                    "CommitAuthorshipAuditWorker: %s already open, skipping.",
                    subject,
                )
                continue

            extra_sample = sorted(extra)[:5]
            logger.warning(
                "CommitAuthorshipAuditWorker: authorship violation for "
                "proposal %s — %d extra path(s) in commit: %s",
                proposal_id,
                len(extra),
                extra_sample,
            )
            await self.post_observation(
                subject=subject,
                payload={
                    "proposal_id": proposal_id,
                    "pre_execution_sha": pre_sha,
                    "post_execution_sha": post_sha,
                    "declared_production": sorted(declared),
                    "extra_paths": sorted(extra),
                    "extra_count": len(extra),
                    "detected_at": datetime.now(UTC).isoformat(),
                    "grounding_adr": "ADR-129",
                },
                status="indeterminate",
            )

        (
            finalization_flagged,
            finalization_suppressed,
        ) = await self._audit_finalization_integrity(blackboard_service)

        (
            degraded_flagged,
            degraded_suppressed,
        ) = await self._audit_consequence_evidence_degraded(blackboard_service)

        await self.post_report(
            subject="commit_authorship_audit_worker.run.complete",
            payload={
                "checked": checked,
                "skipped_no_declared": skipped_no_declared,
                "violations_detected": violations,
                "suppressed": suppressed,
                "finalization_integrity_flagged": finalization_flagged,
                "finalization_integrity_suppressed": finalization_suppressed,
                "consequence_evidence_degraded_flagged": degraded_flagged,
                "consequence_evidence_degraded_suppressed": degraded_suppressed,
            },
        )
        logger.info(
            "CommitAuthorshipAuditWorker: checked=%d skipped=%d "
            "violations=%d suppressed=%d finalization_flagged=%d "
            "degraded_flagged=%d",
            checked,
            skipped_no_declared,
            violations,
            suppressed,
            finalization_flagged,
            degraded_flagged,
        )

    # ID: 326f9bc9-28da-4e46-a2b4-806de8dd1835
    async def _audit_finalization_integrity(
        self, blackboard_service: Any
    ) -> tuple[int, int]:
        """
        ADR-148 D5: flag any completed proposal missing a durable consequence
        record. Returns (flagged, suppressed) for the caller's report.
        """
        from body.services.service_registry import service_registry

        existing = await blackboard_service.fetch_active_finding_subjects_by_prefix(
            "governance.proposal_finalization_integrity::%"
        )

        proposal_svc = await service_registry.get_proposal_supervision_service()
        rows = await proposal_svc.fetch_completed_without_consequence(limit=100)

        flagged = 0
        suppressed = 0
        for row in rows:
            proposal_id = row["proposal_id"]
            subject = f"governance.proposal_finalization_integrity::{proposal_id}"
            if subject in existing:
                suppressed += 1
                logger.debug(
                    "CommitAuthorshipAuditWorker: %s already open, skipping.",
                    subject,
                )
                continue

            flagged += 1
            logger.warning(
                "CommitAuthorshipAuditWorker: finalization integrity violation "
                "for proposal %s — completed without consequence_recorded_at",
                proposal_id,
            )
            await self.post_observation(
                subject=subject,
                payload={
                    "proposal_id": proposal_id,
                    "execution_completed_at": (
                        row["execution_completed_at"].isoformat()
                        if row["execution_completed_at"]
                        else None
                    ),
                    "updated_at": (
                        row["updated_at"].isoformat() if row["updated_at"] else None
                    ),
                    "detected_at": datetime.now(UTC).isoformat(),
                    "grounding_adr": "ADR-148",
                },
                status="indeterminate",
            )

        return flagged, suppressed

    # ID: d24ed4c3-5b7e-4ea2-86c0-b83cb6450c96
    async def _audit_consequence_evidence_degraded(
        self, blackboard_service: Any
    ) -> tuple[int, int]:
        """
        ADR-148 D7 (#790): flag any completed proposal whose consequence
        record was synthesized by the stuck_finalizing roll-forward
        (consequence_source='reaper_reconstructed') rather than captured at
        execution time. Returns (flagged, suppressed) for the caller's report.
        """
        from body.services.service_registry import service_registry

        existing = await blackboard_service.fetch_active_finding_subjects_by_prefix(
            "governance.consequence_evidence_degraded::%"
        )

        proposal_svc = await service_registry.get_proposal_supervision_service()
        rows = await proposal_svc.fetch_completed_with_degraded_consequence(limit=100)

        flagged = 0
        suppressed = 0
        for row in rows:
            proposal_id = row["proposal_id"]
            subject = f"governance.consequence_evidence_degraded::{proposal_id}"
            if subject in existing:
                suppressed += 1
                logger.debug(
                    "CommitAuthorshipAuditWorker: %s already open, skipping.",
                    subject,
                )
                continue

            flagged += 1
            logger.warning(
                "CommitAuthorshipAuditWorker: consequence evidence degraded "
                "for proposal %s — completed on a reaper-reconstructed, "
                "empty consequence record",
                proposal_id,
            )
            await self.post_observation(
                subject=subject,
                payload={
                    "proposal_id": proposal_id,
                    "execution_completed_at": (
                        row["execution_completed_at"].isoformat()
                        if row["execution_completed_at"]
                        else None
                    ),
                    "updated_at": (
                        row["updated_at"].isoformat() if row["updated_at"] else None
                    ),
                    "detected_at": datetime.now(UTC).isoformat(),
                    "grounding_adr": "ADR-148",
                },
                status="indeterminate",
            )

        return flagged, suppressed
