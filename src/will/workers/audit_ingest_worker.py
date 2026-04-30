# src/will/workers/audit_ingest_worker.py
# ID: will.workers.audit_ingest_worker
"""
AuditIngestWorker - Constitutional Compliance Sensing Worker.

Responsibility: Read the most recent audit run findings for rule
ai.prompt.model_required and post each unprocessed violation as a
blackboard finding.

Constitutional standing:
- Declaration:      .intent/workers/audit_ingest_worker.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none (no LLM calls)
- Approval:         false

LAYER: will/workers — sensing worker. Receives CoreContext via
constructor injection (no direct settings imports).
Does not read source files or suggest fixes.
"""

from __future__ import annotations

import re
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# The rule we are ingesting findings for
_TARGET_RULE = "ai.prompt.model_required"

# Blackboard subject prefix for findings posted by this worker
_FINDING_SUBJECT = "ai.prompt.model_required"

# Regex to extract line number from AuditFinding message, e.g. "Line 163: ..."
_LINE_RE = re.compile(r"Line (\d+):")


# ID: bfbdf0ac-487a-4b1b-a9a5-df61a94e12eb
class AuditIngestWorker(Worker):
    """
    Sensing worker. Runs the constitutional auditor scoped to
    ai.prompt.model_required and posts each violation as a blackboard
    finding for downstream processing by PromptExtractorWorker.

    No LLM calls. No file reads beyond what the auditor requires.
    approval_required: false — findings are observations, not actions.
    """

    declaration_name = "audit_ingest_worker"

    def __init__(self, core_context: Any) -> None:
        """
        Args:
            core_context: Initialized CoreContext. Provides auditor_context
                          with repo_path — no direct settings access needed.
        """
        super().__init__()
        self._core_context = core_context

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
    async def run(self) -> None:
        """
        Run the constitutional auditor, filter findings for the target rule,
        deduplicate against existing blackboard entries, and post each new
        violation as a finding.
        """
        await self.post_heartbeat()

        violations = await self._run_audit()

        if not violations:
            await self.post_report(
                subject="audit_ingest_worker.run.complete",
                payload={
                    "violations_found": 0,
                    "message": f"No {_TARGET_RULE} violations detected.",
                },
            )
            logger.info("AuditIngestWorker: no violations found.")
            return

        logger.info(
            "AuditIngestWorker: %d violations found for %s.",
            len(violations),
            _TARGET_RULE,
        )

        existing = await self._fetch_existing_subjects()

        posted = 0
        skipped = 0

        for v in violations:
            subject = f"{_FINDING_SUBJECT}::{v['file_path']}::{v['line_number']}"

            if subject in existing:
                skipped += 1
                logger.debug("AuditIngestWorker: skipping already-posted %s", subject)
                continue

            await self.post_finding(
                subject=subject,
                payload={
                    "rule": _TARGET_RULE,
                    "file_path": v["file_path"],
                    "line_number": v["line_number"],
                    "message": v["message"],
                    "severity": v["severity"],
                    "status": "unprocessed",
                },
            )
            posted += 1
            logger.debug(
                "AuditIngestWorker: posted %s line %s", v["file_path"], v["line_number"]
            )

        await self.post_report(
            subject="audit_ingest_worker.run.complete",
            payload={
                "violations_found": len(violations),
                "posted": posted,
                "skipped_duplicates": skipped,
                "message": (
                    f"Run complete. {posted} findings posted, "
                    f"{skipped} duplicates skipped."
                ),
            },
        )

        logger.info("AuditIngestWorker: %d posted, %d skipped.", posted, skipped)

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _run_audit(self) -> list[dict[str, Any]]:
        """
        Run the full constitutional audit via the injected AuditorContext,
        extract findings["findings"] list, filter to target rule, and return
        normalized dicts with line numbers extracted from the message string.
        """
        from mind.governance.auditor import ConstitutionalAuditor

        auditor_context = self._core_context.auditor_context
        auditor = ConstitutionalAuditor(auditor_context)

        # run_full_audit_async() returns a dict:
        # {"findings": [AuditFinding, ...], "stats": ..., "verdict": ...}
        result = await auditor.run_full_audit_async()
        raw_findings = result["findings"]

        violations = []
        for finding in raw_findings:
            # Normalize: AuditFinding dataclass or dict
            if isinstance(finding, dict):
                check_id = finding.get("check_id", "")
                file_path = finding.get("file_path")
                message = finding.get("message", "")
                severity = str(finding.get("severity", "error"))
            else:
                check_id = getattr(finding, "check_id", "")
                file_path = getattr(finding, "file_path", None)
                message = getattr(finding, "message", "")
                severity = str(getattr(finding, "severity", "error"))

            if check_id != _TARGET_RULE:
                continue
            if not file_path:
                continue

            # line_number is None on AuditFinding — extract from message
            # Message format: "Line 163: direct call to 'make_request_async()' ..."
            line_number: int | None = None
            m = _LINE_RE.search(message)
            if m:
                line_number = int(m.group(1))

            if line_number is None:
                logger.warning(
                    "AuditIngestWorker: could not extract line number from: %s", message
                )
                continue

            violations.append(
                {
                    "file_path": file_path,
                    "line_number": line_number,
                    "message": message,
                    "severity": severity,
                }
            )

        return violations

    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Query the blackboard for already-posted subjects from this worker.
        Used for deduplication — avoids re-posting the same violation across runs.
        """
        svc = await self._core_context.registry.get_blackboard_service()
        return await svc.fetch_open_finding_subjects_by_worker(
            str(self._worker_uuid), f"{_FINDING_SUBJECT}::%"
        )
