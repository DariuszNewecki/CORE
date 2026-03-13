# src/will/workers/audit_violation_sensor.py
# ID: will.workers.audit_violation_sensor
"""
AuditViolationSensor - Constitutional Compliance Sensing Worker.

Responsibility: Run the constitutional auditor scoped to a configured target
rule and post each unprocessed violation as a blackboard finding for downstream
processing by ViolationRemediatorWorker.

Constitutional standing:
- Declaration:      .intent/workers/audit_violation_sensor.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none (no LLM calls)
- Approval:         false

LAYER: will/workers — sensing worker. Receives CoreContext via constructor
injection. No file writes. No LLM. Pure perception.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Blackboard subject prefix for findings posted by this worker
_FINDING_SUBJECT = "audit.violation"


# ID: 7199fd0e-a8ed-40e6-b7f1-5718d6b79ae4
class AuditViolationSensor(Worker):
    """
    Sensing worker. Runs the constitutional auditor scoped to a configured
    target rule and posts each unprocessed violation as a blackboard finding
    for downstream processing by ViolationRemediatorWorker.

    No LLM calls. No file writes. approval_required: false.

    Args:
        core_context: Initialized CoreContext.
        target_rule: Audit rule ID to scope the sensor to
                     (e.g. 'purity.no_ast_duplication').
        dry_run: If True, posts findings tagged dry_run=True so the
                 remediator will not apply any changes.
    """

    declaration_name = "audit_violation_sensor"

    def __init__(
        self,
        core_context: Any,
        target_rule: str,
        dry_run: bool = True,
    ) -> None:
        super().__init__()
        self._core_context = core_context
        self._target_rule = target_rule
        self._dry_run = dry_run

    # ID: avs-run-001
    # ID: 9bf16dc0-5239-4e2b-8085-09732bba745a
    async def run(self) -> None:
        """
        Run the constitutional auditor, filter findings for the target rule,
        deduplicate against existing blackboard entries, and post each new
        violation as a finding.
        """
        await self.post_heartbeat()

        logger.info(
            "AuditViolationSensor: scanning for rule '%s' (dry_run=%s)",
            self._target_rule,
            self._dry_run,
        )

        violations = await self._run_audit()

        if not violations:
            await self.post_report(
                subject="audit_violation_sensor.run.complete",
                payload={
                    "target_rule": self._target_rule,
                    "violations_found": 0,
                    "dry_run": self._dry_run,
                    "message": f"No '{self._target_rule}' violations detected.",
                },
            )
            logger.info(
                "AuditViolationSensor: no violations found for '%s'.",
                self._target_rule,
            )
            return

        logger.info(
            "AuditViolationSensor: %d violations found for '%s'.",
            len(violations),
            self._target_rule,
        )

        existing = await self._fetch_existing_subjects()

        posted = 0
        skipped = 0

        for v in violations:
            subject = f"{_FINDING_SUBJECT}::{self._target_rule}::{v['file_path']}"

            if subject in existing:
                skipped += 1
                logger.debug(
                    "AuditViolationSensor: skipping already-posted %s", subject
                )
                continue

            await self.post_finding(
                subject=subject,
                payload={
                    "rule": self._target_rule,
                    "file_path": v["file_path"],
                    "line_number": v.get("line_number"),
                    "message": v["message"],
                    "severity": v["severity"],
                    "dry_run": self._dry_run,
                    "status": "unprocessed",
                },
            )
            posted += 1
            logger.debug("AuditViolationSensor: posted finding for %s", v["file_path"])

        await self.post_report(
            subject="audit_violation_sensor.run.complete",
            payload={
                "target_rule": self._target_rule,
                "violations_found": len(violations),
                "posted": posted,
                "skipped_duplicates": skipped,
                "dry_run": self._dry_run,
                "message": (
                    f"Run complete. {posted} findings posted, "
                    f"{skipped} duplicates skipped."
                ),
            },
        )

        logger.info("AuditViolationSensor: %d posted, %d skipped.", posted, skipped)

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    async def _run_audit(self) -> list[dict[str, Any]]:
        """
        Run a filtered constitutional audit for the target rule and return
        normalized violation dicts.

        Mirrors the pattern used by `core-admin code audit --rule <id>`:
          1. Inject db_session into auditor_context (required for fingerprints)
          2. load_knowledge_graph()
          3. run_filtered_audit(rule_ids=[target_rule])
        """
        from mind.governance.filtered_audit import run_filtered_audit
        from shared.infrastructure.database.session_manager import get_session

        auditor_context = self._core_context.auditor_context

        async with get_session() as session:
            auditor_context.db_session = session
            await auditor_context.load_knowledge_graph()
            raw_findings, _, _ = await run_filtered_audit(
                auditor_context, rule_ids=[self._target_rule]
            )
            auditor_context.db_session = None

        violations = []
        for finding in raw_findings:
            if isinstance(finding, dict):
                file_path = finding.get("file_path")
                message = finding.get("message", "")
                severity = str(finding.get("severity", "warning"))
                line_number = finding.get("line_number")
                ctx = finding.get("context", {})
            else:
                file_path = getattr(finding, "file_path", None)
                message = getattr(finding, "message", "")
                severity = str(getattr(finding, "severity", "warning"))
                line_number = getattr(finding, "line_number", None)
                ctx = getattr(finding, "context", {}) or {}

            # AST duplication findings carry symbol pair in context, not file_path.
            # Derive file_path from symbol_a module path (dotted → src/.../.py).
            if not file_path:
                symbol_a = ctx.get("symbol_a", "")
                # Try context-level file keys first
                file_path = (
                    ctx.get("file_path") or ctx.get("file") or ctx.get("module_path")
                )
                # Fall back: derive from symbol_a which is "module.ClassName.method"
                # or just use the message context if available
                if not file_path and symbol_a:
                    # symbol_a comes from a.get("name") in _create_duplication_finding.
                    # In symbols_map rows, this maps to the "qualname" column.
                    symbols_map = getattr(
                        self._core_context.auditor_context, "symbols_map", {}
                    )
                    for sym_path, sym_data in symbols_map.items():
                        qualname = sym_data.get("qualname", "") or sym_data.get(
                            "name", ""
                        )
                        if qualname == symbol_a or sym_path.endswith(f".{symbol_a}"):
                            module = sym_data.get("module", "")
                            if module:
                                file_path = "src/" + module.replace(".", "/") + ".py"
                            break

            if not file_path:
                # Last resort: include the finding without a specific file
                # so remediator can use the symbol pair from context
                file_path = f"__symbol_pair__{ctx.get('symbol_a', 'unknown')}"

            violations.append(
                {
                    "file_path": file_path,
                    "line_number": line_number,
                    "message": message,
                    "severity": severity,
                    "context": ctx,
                }
            )

        return violations

    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Query the blackboard for already-posted subjects for this rule.
        Used for deduplication across runs.
        """
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

        prefix = f"{_FINDING_SUBJECT}::{self._target_rule}::%"

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT subject FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status NOT IN ('resolved', 'abandoned', 'dry_run_complete')
                    """
                ),
                {"prefix": prefix},
            )
            return {row[0] for row in result.fetchall()}
