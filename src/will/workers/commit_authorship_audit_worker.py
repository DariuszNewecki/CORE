# src/will/workers/commit_authorship_audit_worker.py
"""
CommitAuthorshipAuditWorker — ADR-129 D4 authorship integrity sensor.

For each autonomous commit in the recent consequence log, verifies that
the actual git diff (files_changed between pre- and post-execution SHAs)
is a subset of the declared production set (declared_production). Any path
in the diff that is NOT in declared_production indicates staging contamination:
bytes from a concurrent session were swept into the autonomous commit, violating
ADR-101 D1 authorship integrity.

Posts governance.commit_authorship_integrity::{proposal_id} findings for
violations; audit posture is 'reporting' (ADR-129 D5, no auto-remediation).

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
    Governance worker. Compares declared_production (what commit_paths was
    authorized to commit) against the actual git diff (what was committed)
    for each autonomous proposal in the last 7 days. Detects staging
    contamination introduced by the pre-ADR-129-D1 gap in commit_paths.

    Rows written before ADR-129 was deployed have declared_production = []
    (the column default). The worker skips those rows as unverifiable —
    it cannot reconstruct what the action declared at the time, so treating
    them as violations would produce false positives. Coverage begins from
    the first proposal executed after the declared_production column was
    populated (after migration 20260628_adr129_add_declared_production_
    to_proposal_consequences.sql was applied).

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

        await self.post_report(
            subject="commit_authorship_audit_worker.run.complete",
            payload={
                "checked": checked,
                "skipped_no_declared": skipped_no_declared,
                "violations_detected": violations,
                "suppressed": suppressed,
            },
        )
        logger.info(
            "CommitAuthorshipAuditWorker: checked=%d skipped=%d "
            "violations=%d suppressed=%d",
            checked,
            skipped_no_declared,
            violations,
            suppressed,
        )
