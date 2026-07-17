# src/will/workers/violation_remediator_body/worker.py
"""
ViolationRemediator - Constitutional Compliance Acting Worker.

Responsibility: claim open audit-violation findings for its target rule
from the blackboard and run each violating file's remediation ceremony
(architectural context, RemoteCoder fix, Crate/Canary/apply/commit) via
will.remediation.RemediationCeremony.

ADR-153: the ceremony itself was extracted to will/remediation/ so that
ViolationExecutorWorker (and CLI file-mode) no longer need to import and
instantiate this class — a Worker subclass — to run it. This class keeps
only the claim/group/report loop; RemediationCeremony owns the per-file
work, and posts/marks through a WorkerRemediationBlackboard wrapping this
worker's own, genuinely-registered identity. No caller_uuid substitution
— nobody instantiates this class on another worker's behalf anymore.

Constitutional standing:
- Declaration:      .intent/workers/violation_remediator.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  llm.remote_coder, file.read, crate.create,
                    canary.validate, crate.apply, git.commit
- Approval:         true

LAYER: body/workers - acting worker. Receives CoreContext via constructor
injection. All src/ writes via ActionExecutor -> Crate -> Canary -> apply.
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.base import Worker
from will.remediation import RemediationCeremony, WorkerRemediationBlackboard


logger = getLogger(__name__)

# Minimum role detection confidence required to proceed in write mode —
# still resolved here even though _plan_file itself moved: kept for
# operational_config parity with the rest of this worker's config surface.
_CFG = load_operational_config().workers.violation_remediator


# ID: bb52f62a-45c9-47a4-9ff8-788b0c6ca4f1
class ViolationRemediator(Worker):
    """
    Acting worker. Claims open audit violation findings from the blackboard
    and runs the extracted remediation ceremony (RemediationCeremony) for
    each violating file.

    In dry-run mode (write=False): planning, LLM, and Canary run,
    nothing is applied, proposed fix is posted to the blackboard for human
    review.

    In write mode (write=True): full ceremony - apply + git commit.

    Args:
        core_context: Initialized CoreContext.
        target_rule: Only process findings for this rule ID.
        write: If False, dry-run mode - no src/ writes, no commits.
    """

    declaration_name = "violation_remediator_body"

    def __init__(
        self,
        core_context: Any,
        target_rule: str | None = None,
        write: bool = False,
    ) -> None:
        super().__init__()
        self._ctx = core_context
        self._target_rule = target_rule
        self._write = write

    # ID: 83141abe-9611-497f-a14c-29c5cf04d305
    async def run(self) -> None:
        """
        Main execution loop. Groups findings by file, runs each file
        through RemediationCeremony (or dry-run variant).
        """
        await self.post_heartbeat()

        mode = "WRITE" if self._write else "DRY-RUN"
        logger.info(
            "ViolationRemediator: starting [%s] for rule '%s'",
            mode,
            self._target_rule,
        )

        findings = await self._claim_open_findings()

        if not findings:
            await self.post_report(
                subject="violation_remediator.run.complete",
                payload={
                    "rule": self._target_rule,
                    "write": self._write,
                    "processed": 0,
                    "message": "No open violation findings to remediate.",
                },
            )
            logger.info("ViolationRemediator: no open findings.")
            return

        by_file: dict[str, list[dict[str, Any]]] = {}
        for finding in findings:
            payload = finding.get("payload") or {}
            file_path = str(payload.get("file_path") or "").strip()

            if not file_path:
                logger.warning(
                    "ViolationRemediator: skipping finding %s with missing file_path",
                    finding.get("id"),
                )
                continue

            by_file.setdefault(file_path, []).append(finding)

        logger.info(
            "ViolationRemediator: %d findings across %d files [%s].",
            len(findings),
            len(by_file),
            mode,
        )

        blackboard = WorkerRemediationBlackboard(self, self._ctx)
        ceremony = RemediationCeremony(
            self._ctx, self._target_rule, self._write, blackboard
        )

        succeeded = 0
        failed = 0

        for file_path, file_findings in by_file.items():
            ok = await ceremony.process_file(file_path, file_findings)
            if ok:
                succeeded += 1
            else:
                failed += 1

        await self.post_report(
            subject="violation_remediator.run.complete",
            payload={
                "rule": self._target_rule,
                "write": self._write,
                "succeeded": succeeded,
                "failed": failed,
                "message": f"[{mode}] {succeeded} files processed, {failed} failed.",
            },
        )
        logger.info(
            "ViolationRemediator: [%s] %d succeeded, %d failed.",
            mode,
            succeeded,
            failed,
        )

    # ID: 6c1e8f5a-9d2b-4e73-a084-3f6b7c9e1a52
    async def _claim_open_findings(self) -> list[dict[str, Any]]:
        """
        Atomically claim open audit-violation findings for the target rule,
        ordered by severity (critical first) then by creation time.

        Uses FOR UPDATE SKIP LOCKED to prevent double-claiming across
        concurrent worker instances. Subject discrimination derives from
        `audit_violation_like_patterns()` per ADR-091 D5 Phase 3 — no
        static prefix.
        """
        from shared.infrastructure.intent.audit_namespaces import (
            audit_violation_like_patterns,
        )

        bb = await self._ctx.registry.get_blackboard_service()
        return await bb.claim_findings_by_patterns(
            patterns=audit_violation_like_patterns(),
            limit=_CFG.claim_limit,
            claimed_by=self._worker_uuid,
        )
