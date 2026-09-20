# src/will/workers/audit_ingest_worker.py
"""
AuditIngestWorker - Constitutional Compliance Sensing Worker.

Responsibility: Run a *filtered* constitutional audit scoped to the single
rule ai.prompt.model_required and post each unprocessed violation as a
blackboard finding.

Filtered, not full: a full audit executes every mapped engine, including
llm_gate, whose verdicts this worker discards — and without an injected DB
session the ADR-044 verdict cache is ineligible, so every cycle re-bought
the same judged (file, rule) pairs from the paid LocalCoder resource (~10 calls
per run, 48 runs/day, since 2026-05). The filtered path via
will.audit_violation.normalizer runs only the target rule (an ast_gate
rule) inside a service_registry session — the "no LLM calls" declaration
below is true by construction, not by cache behaviour.

Constitutional standing:
- Declaration:      .intent/workers/audit_ingest_worker.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none (no LLM calls — filtered audit, target rule only)
- Approval:         false

LAYER: will/workers — sensing worker. Receives CoreContext via
constructor injection (no direct settings imports).
Does not read source files or suggest fixes.
"""

from __future__ import annotations

import re
from typing import Any

from shared.infrastructure.intent.rule_registry import get_rule_registry
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# The rule we are ingesting findings for — validated against .intent/ at import time
_TARGET_RULE = get_rule_registry()["ai.prompt.model_required"]

# Blackboard sub-namespace mirrors the rule this worker tracks
_SUB_NAMESPACE = _TARGET_RULE

# Artifact type these findings are about (Python source files).
# ADR-091 D2: subjects are <artifact_type>::<sub_namespace>::<identity_key_value>.
_ARTIFACT_TYPE = "python"

# Regex to extract line number from AuditFinding message, e.g. "Line 163: ..."
_LINE_RE = re.compile(r"Line (\d+):")


# ID: bfbdf0ac-487a-4b1b-a9a5-df61a94e12eb
class AuditIngestWorker(Worker):
    """
    Sensing worker. Runs a filtered constitutional audit scoped to
    ai.prompt.model_required and posts each violation as a blackboard
    finding for downstream processing by PromptExtractorWorker.

    No LLM calls: the filtered audit executes only the target rule's
    engine (ast_gate). No file reads beyond what the auditor requires.
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

    # ID: 101d7dc5-c889-4b28-bd47-0e4dcc1047cd
    async def run(self) -> None:
        """
        Run a filtered constitutional audit for the target rule,
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
            identity_key = f"{v['file_path']}::{v['line_number']}"
            subject = f"{_ARTIFACT_TYPE}::{_SUB_NAMESPACE}::{identity_key}"

            if subject in existing:
                skipped += 1
                logger.debug("AuditIngestWorker: skipping already-posted %s", subject)
                continue

            await self.post_artifact_finding(
                artifact_type=_ARTIFACT_TYPE,
                sub_namespace=_SUB_NAMESPACE,
                identity_key_value=identity_key,
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
        Run a filtered constitutional audit for the target rule only and
        return normalized dicts with line numbers.

        Routes through will.audit_violation.normalizer.normalize_audit_findings
        — the same filtered-audit-inside-a-session path the audit_sensor_*
        family uses — so only ai.prompt.model_required's engine executes.
        Never ConstitutionalAuditor.run_full_audit_async(): that runs every
        mapped engine, llm_gate included, and this worker declares no LLM.
        """
        from will.audit_violation.normalizer import normalize_audit_findings

        raw_findings = await normalize_audit_findings(
            self._core_context,
            rule_namespace=_TARGET_RULE,
            rule_ids=[_TARGET_RULE],
        )

        violations = []
        for finding in raw_findings:
            # Filtered audit only ran the target rule, but keep the check —
            # the normalizer falls back to rule_namespace for findings that
            # arrive without a check_id.
            if finding.get("rule_id") != _TARGET_RULE:
                continue
            file_path = finding.get("file_path")
            if not file_path or str(file_path).startswith("__symbol_pair__"):
                continue
            message = finding.get("message", "")
            severity = str(finding.get("severity", "error"))

            # line_number is usually None on AuditFinding — fall back to the
            # message text. Message format: "Line 163: direct call to ..."
            line_number: int | None = finding.get("line_number")
            if line_number is None:
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
            str(self._worker_uuid), f"{_ARTIFACT_TYPE}::{_SUB_NAMESPACE}::%"
        )
