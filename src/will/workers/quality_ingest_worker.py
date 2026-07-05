# src/will/workers/quality_ingest_worker.py
"""
QualityIngestWorker — quality.* audit finding sensor (ADR-098 D5 / closes #605).

Responsibility: Run the constitutional auditor, extract findings for
quality.* rules listed in .intent/enforcement/config/audit_ingest.yaml,
apply the D5 cap constraint (top-N by issue_count descending per rule),
deduplicate against existing blackboard subjects, and post each new
finding for downstream visibility and eventual remediation.

Constitutional standing:
- Declaration:      .intent/workers/quality_ingest_worker.yaml
- Class:            acting
- Phase:            audit
- Permitted tools:  none (no LLM calls, no file writes)
- Approval:         false

Wiring constraint (ADR-098 D5):
- At most quality_ingest_cap findings posted per (rule, audit run).
- When cap fires, top-N ordered by context.issue_count descending.
- Dedup is across ALL workers by subject prefix — prevents re-posting
  across daemon generations when UUIDs differ.
- Quality rules to wire are governed in audit_ingest.yaml, not here.

Subject format (ADR-091 D2 convention):
  audit.violation::{rule_id}::{file_path}

LAYER: will/workers — sensing worker. CoreContext injected via constructor.
No direct DB imports. No LLM. No file writes.
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.intent.audit_ingest_config import load_audit_ingest_config
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Subject namespace prefix for quality ingest findings.
# Used for prefix-based dedup (fetches all open subjects in this namespace).
_SUBJECT_PREFIX = "audit.violation::quality."


# ID: 29c9ba19-cb24-4896-ba5a-7f9d572acdc9
class QualityIngestWorker(Worker):
    """
    Sensing worker for quality.* audit rules.

    Runs the full constitutional audit, extracts quality.* findings for
    rules declared in audit_ingest.yaml, applies the D5 fanout cap, and
    posts each new finding to the blackboard.

    No LLM calls. No file writes. approval_required: false.
    """

    declaration_name = "quality_ingest_worker"

    def __init__(self, core_context: Any) -> None:
        super().__init__(declaration_name=self.declaration_name)
        self._core_context = core_context

    # ID: 2b871537-2ed7-4ac7-9d55-fab6aa991470
    async def run(self) -> None:
        """Run the quality ingest pipeline.

        1. Load config (enabled rules, cap).
        2. Run full audit and filter quality findings for enabled rules.
        3. Apply D5 cap per rule (top-N by issue_count descending).
        4. Dedup against existing blackboard subjects.
        5. Post each new finding; report completion summary.
        """
        await self.post_heartbeat()

        config = load_audit_ingest_config()
        if not config.enabled_rules:
            await self.post_report(
                subject="quality_ingest_worker.run.complete",
                payload={
                    "enabled_rules": [],
                    "posted": 0,
                    "skipped_duplicate": 0,
                    "skipped_cap": 0,
                    "message": "No quality rules enabled in audit_ingest.yaml.",
                },
            )
            logger.info("QualityIngestWorker: no enabled rules — nothing to post.")
            return

        all_findings = await self._run_audit()
        if not all_findings:
            await self.post_report(
                subject="quality_ingest_worker.run.complete",
                payload={
                    "enabled_rules": config.enabled_rules,
                    "posted": 0,
                    "skipped_duplicate": 0,
                    "skipped_cap": 0,
                    "message": "Audit returned no quality findings.",
                },
            )
            return

        capped = self._apply_cap(all_findings, config)
        skipped_cap = sum(len(v) for v in all_findings.values()) - sum(
            len(v) for v in capped.values()
        )

        existing = await self._fetch_existing_subjects()

        posted = 0
        skipped_dup = 0
        for rule_id, findings in capped.items():
            for f in findings:
                subject = f"audit.violation::{rule_id}::{f['file_path']}"
                if subject in existing:
                    skipped_dup += 1
                    logger.debug("QualityIngestWorker: skipping duplicate %s", subject)
                    continue

                await self.post_finding(
                    subject=subject,
                    payload={
                        "rule": rule_id,
                        "file_path": f["file_path"],
                        "message": f["message"],
                        "issue_count": f.get("issue_count", 1),
                        "sample_issues": f.get("sample_issues", []),
                        "tool": f.get("tool", ""),
                        "status": "unprocessed",
                    },
                    resolution_mechanism="reaudit",
                )
                posted += 1
                logger.debug("QualityIngestWorker: posted %s", subject)

        await self.post_report(
            subject="quality_ingest_worker.run.complete",
            payload={
                "enabled_rules": config.enabled_rules,
                "posted": posted,
                "skipped_duplicate": skipped_dup,
                "skipped_cap": skipped_cap,
                "message": (
                    f"Run complete. {posted} findings posted, "
                    f"{skipped_dup} duplicates skipped, "
                    f"{skipped_cap} capped."
                ),
            },
        )
        logger.info(
            "QualityIngestWorker: %d posted, %d skipped (dup), %d capped.",
            posted,
            skipped_dup,
            skipped_cap,
        )

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    # ID: f743a187-715e-4f63-8176-d0347fad7e5b
    async def _run_audit(self) -> dict[str, list[dict[str, Any]]]:
        """Run the full audit and return findings grouped by quality rule ID.

        Returns a dict of {rule_id: [finding_dict, ...]} for each enabled
        rule that produced at least one finding. Each finding dict carries:
          file_path, message, issue_count, sample_issues, tool.
        """
        from mind.governance.auditor import ConstitutionalAuditor

        config = load_audit_ingest_config()
        enabled = set(config.enabled_rules)

        auditor_context = self._core_context.auditor_context
        auditor = ConstitutionalAuditor(auditor_context)
        result = await auditor.run_full_audit_async()
        raw_findings = result.get("findings", [])

        grouped: dict[str, list[dict[str, Any]]] = {}
        for finding in raw_findings:
            if isinstance(finding, dict):
                check_id = finding.get("check_id", "")
                file_path = finding.get("file_path") or ""
                message = finding.get("message", "")
                context = finding.get("context") or {}
            else:
                check_id = getattr(finding, "check_id", "")
                file_path = getattr(finding, "file_path", None) or ""
                message = getattr(finding, "message", "")
                context = getattr(finding, "context", None) or {}

            if check_id not in enabled:
                continue
            if not file_path:
                continue

            entry = {
                "file_path": file_path,
                "message": message,
                "issue_count": context.get("issue_count", 1),
                "sample_issues": context.get("sample_issues", []),
                "tool": context.get("tool", ""),
            }
            grouped.setdefault(check_id, []).append(entry)

        return grouped

    # ID: feb74607-bfba-46ec-a418-1631c132e526
    def _apply_cap(
        self,
        grouped: dict[str, list[dict[str, Any]]],
        config: Any,
    ) -> dict[str, list[dict[str, Any]]]:
        """Apply the D5 per-rule cap ordered by issue_count descending.

        For each rule, keep at most quality_ingest_cap findings, selecting
        those with the highest issue_count first (most-impactful files first).
        """
        cap = config.quality_ingest_cap
        result: dict[str, list[dict[str, Any]]] = {}
        for rule_id, findings in grouped.items():
            sorted_findings = sorted(
                findings, key=lambda f: f.get("issue_count", 1), reverse=True
            )
            result[rule_id] = sorted_findings[:cap]
        return result

    # ID: fe2d3019-fdde-4870-8ec0-835e1a0f3a29
    async def _fetch_existing_subjects(self) -> set[str]:
        """Fetch existing blackboard subjects for the quality namespace.

        Dedup is cross-worker by subject prefix to prevent re-posting across
        daemon generations. Returns all subjects in any non-terminal status.
        """
        svc = await self._core_context.registry.get_blackboard_service()
        return await svc.fetch_active_finding_subjects_by_prefix(_SUBJECT_PREFIX)
