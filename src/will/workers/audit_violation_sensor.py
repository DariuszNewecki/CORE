# src/will/workers/audit_violation_sensor.py
# ID: will.workers.audit_violation_sensor
"""
AuditViolationSensor - Constitutional Compliance Sensing Worker.

Responsibility: Run the constitutional auditor scoped to a configured rule
namespace and post each unprocessed violation as a blackboard finding for
downstream processing by ViolationRemediatorWorker.

Constitutional standing:
- Declaration:      .intent/workers/audit_sensor_<namespace>.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none (no LLM calls)
- Approval:         false

Design:
- One class, many declarations. Each .intent/workers/audit_sensor_*.yaml
  declares a rule_namespace prefix (e.g. "purity", "logic"). The daemon
  passes declaration_name and rule_namespace as constructor kwargs.
- Rule IDs within the namespace are resolved dynamically from
  IntentRepository._rule_index at runtime — no hardcoding.
- Adding a rule to an existing namespace automatically brings it into scope.

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
    Sensing worker. Runs the constitutional auditor scoped to all rules
    within a declared rule_namespace and posts each unprocessed violation
    as a blackboard finding for downstream processing by ViolationRemediatorWorker.

    One class backs multiple .intent/workers/ declarations — one per namespace.
    The daemon injects declaration_name and rule_namespace at construction time.

    No LLM calls. No file writes. approval_required: false.

    Args:
        core_context:     Initialized CoreContext.
        declaration_name: YAML stem of the worker declaration (e.g. "audit_sensor_purity").
                          Passed by daemon loader; overrides the class-level default.
        rule_namespace:   Rule ID prefix to scope this sensor to
                          (e.g. "purity", "logic", "architecture.channels").
                          Resolved dynamically against IntentRepository at runtime.
        dry_run:          If True, posts findings tagged dry_run=True so the
                          remediator will not apply any changes.
    """

    declaration_name = ""  # Set per-instance by daemon via constructor kwarg

    def __init__(
        self,
        core_context: Any,
        declaration_name: str,
        rule_namespace: str,
        dry_run: bool = True,
    ) -> None:
        super().__init__(declaration_name=declaration_name)
        self._core_context = core_context
        self._rule_namespace = rule_namespace
        self._dry_run = dry_run

    # ID: 9bf16dc0-5239-4e2b-8085-09732bba745a
    async def run(self) -> None:
        """
        Resolve rule IDs for the namespace, run the constitutional auditor,
        deduplicate against existing blackboard entries, and post each new
        violation as a finding.
        """
        await self.post_heartbeat()

        rule_ids = self._resolve_rule_ids()
        if not rule_ids:
            await self.post_report(
                subject="audit_violation_sensor.run.complete",
                payload={
                    "rule_namespace": self._rule_namespace,
                    "rule_ids_resolved": 0,
                    "message": f"No rules found for namespace '{self._rule_namespace}'.",
                },
            )
            logger.warning(
                "AuditViolationSensor: no rules resolved for namespace '%s'.",
                self._rule_namespace,
            )
            return

        logger.info(
            "AuditViolationSensor[%s]: resolved %d rules: %s",
            self._rule_namespace,
            len(rule_ids),
            rule_ids,
        )

        violations = await self._run_audit(rule_ids)

        if not violations:
            await self.post_report(
                subject="audit_violation_sensor.run.complete",
                payload={
                    "rule_namespace": self._rule_namespace,
                    "rule_ids_resolved": len(rule_ids),
                    "violations_found": 0,
                    "dry_run": self._dry_run,
                    "message": f"No violations detected in namespace '{self._rule_namespace}'.",
                },
            )
            logger.info(
                "AuditViolationSensor[%s]: no violations found.",
                self._rule_namespace,
            )
            return

        logger.info(
            "AuditViolationSensor[%s]: %d violations found.",
            self._rule_namespace,
            len(violations),
        )

        existing = await self._fetch_existing_subjects()

        posted = 0
        skipped = 0

        for v in violations:
            rule_id = v.get("rule_id", self._rule_namespace)
            subject = f"{_FINDING_SUBJECT}::{rule_id}::{v['file_path']}"

            if subject in existing:
                skipped += 1
                logger.debug(
                    "AuditViolationSensor: skipping already-posted %s", subject
                )
                continue

            await self.post_finding(
                subject=subject,
                payload={
                    "rule_namespace": self._rule_namespace,
                    "rule": rule_id,
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
                "rule_namespace": self._rule_namespace,
                "rule_ids_resolved": len(rule_ids),
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

        logger.info(
            "AuditViolationSensor[%s]: %d posted, %d skipped.",
            self._rule_namespace,
            posted,
            skipped,
        )

    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------

    def _resolve_rule_ids(self) -> list[str]:
        """
        Dynamically resolve all rule IDs matching the declared namespace prefix
        from IntentRepository._rule_index.

        This is the key constitutional mechanism: rules are discovered from
        .intent/ at runtime, not hardcoded. Adding a rule to an existing
        namespace automatically brings it into this sensor's scope.
        """
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        try:
            repo = get_intent_repository()
            return sorted(
                rid
                for rid in repo._rule_index
                if rid == self._rule_namespace
                or rid.startswith(f"{self._rule_namespace}.")
            )
        except Exception as e:
            logger.error(
                "AuditViolationSensor: failed to resolve rule IDs for namespace '%s': %s",
                self._rule_namespace,
                e,
            )
            return []

    async def _run_audit(self, rule_ids: list[str]) -> list[dict[str, Any]]:
        """
        Run a filtered constitutional audit for the resolved rule IDs and
        return normalized violation dicts.
        """
        from mind.governance.filtered_audit import run_filtered_audit
        from shared.infrastructure.database.session_manager import get_session

        auditor_context = self._core_context.auditor_context

        async with get_session() as session:
            auditor_context.db_session = session
            await auditor_context.load_knowledge_graph()
            raw_findings, _, _ = await run_filtered_audit(
                auditor_context, rule_ids=rule_ids
            )
            auditor_context.db_session = None

        violations = []
        for finding in raw_findings:
            if isinstance(finding, dict):
                file_path = finding.get("file_path")
                message = finding.get("message", "")
                severity = str(finding.get("severity", "warning"))
                line_number = finding.get("line_number")
                rule_id = finding.get("check_id", self._rule_namespace)
                ctx = finding.get("context", {})
            else:
                file_path = getattr(finding, "file_path", None)
                message = getattr(finding, "message", "")
                severity = str(getattr(finding, "severity", "warning"))
                line_number = getattr(finding, "line_number", None)
                rule_id = getattr(finding, "check_id", self._rule_namespace)
                ctx = getattr(finding, "context", {}) or {}

            if not file_path:
                symbol_a = ctx.get("symbol_a", "")
                file_path = (
                    ctx.get("file_path") or ctx.get("file") or ctx.get("module_path")
                )
                if not file_path and symbol_a:
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
                file_path = f"__symbol_pair__{ctx.get('symbol_a', 'unknown')}"

            violations.append(
                {
                    "file_path": file_path,
                    "line_number": line_number,
                    "message": message,
                    "severity": severity,
                    "rule_id": rule_id,
                    "context": ctx,
                }
            )

        return violations

    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Query the blackboard for already-posted subjects for this namespace.
        Used for deduplication across runs.
        """
        from sqlalchemy import text

        from shared.infrastructure.database.session_manager import get_session

        prefix = f"{_FINDING_SUBJECT}::{self._rule_namespace}.%"

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
