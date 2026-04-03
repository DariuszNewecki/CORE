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

Deduplication contract:
- Dedup is by subject string across ALL workers, not per-worker-UUID.
- This prevents different instances of the same logical sensor (e.g. old
  and new daemon generations) from re-posting the same violation.
- A finding is considered a duplicate if a blackboard entry with the same
  subject exists in any non-terminal status (not resolved or abandoned).

Filtering contract:
- Only findings with a real Python source file path are posted.
  Sentinels like "System", "DB", "unknown", "__symbol_pair__*" indicate
  project-scope or unresolvable violations that the remediator cannot act on.
- Only findings whose check_id is a proper rule ID are posted.
  Enforcement mapping file paths (containing "/" and ending in ".yaml"/".json")
  are auditor internals leaking into the finding — they are dropped.

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

# File path values produced by the auditor for project-scope or unresolvable
# findings. The remediator cannot open these as source files — skip them.
_SENTINEL_FILE_PATHS: frozenset[str] = frozenset(
    {
        "System",
        "system",
        "DB",
        "db",
        "unknown",
        "none",
        "None",
        "",
    }
)


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

        raw_violations = await self._run_audit(rule_ids)
        violations = self._filter_violations(raw_violations)

        filtered_out = len(raw_violations) - len(violations)
        if filtered_out:
            logger.info(
                "AuditViolationSensor[%s]: filtered %d unactionable violations "
                "(sentinel file paths or malformed rule IDs).",
                self._rule_namespace,
                filtered_out,
            )

        if not violations:
            await self.post_report(
                subject="audit_violation_sensor.run.complete",
                payload={
                    "rule_namespace": self._rule_namespace,
                    "rule_ids_resolved": len(rule_ids),
                    "violations_found": 0,
                    "filtered_unactionable": filtered_out,
                    "dry_run": self._dry_run,
                    "message": (
                        f"No actionable violations in namespace '{self._rule_namespace}'."
                    ),
                },
            )
            logger.info(
                "AuditViolationSensor[%s]: no actionable violations found.",
                self._rule_namespace,
            )
            return

        logger.info(
            "AuditViolationSensor[%s]: %d actionable violations.",
            self._rule_namespace,
            len(violations),
        )

        # Dedup by subject — across ALL workers, not just this instance.
        # This prevents different daemon generations from re-posting the same
        # violation when the sensor restarts with a new UUID.
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
                "violations_found": len(raw_violations),
                "filtered_unactionable": filtered_out,
                "posted": posted,
                "skipped_duplicates": skipped,
                "dry_run": self._dry_run,
                "message": (
                    f"Run complete. {posted} findings posted, "
                    f"{skipped} duplicates skipped, "
                    f"{filtered_out} unactionable filtered."
                ),
            },
        )

        logger.info(
            "AuditViolationSensor[%s]: %d posted, %d skipped, %d filtered.",
            self._rule_namespace,
            posted,
            skipped,
            filtered_out,
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
        from body.services.service_registry import service_registry
        from mind.governance.filtered_audit import run_filtered_audit

        auditor_context = self._core_context.auditor_context

        async with service_registry.session() as session:
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

    def _filter_violations(
        self, violations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Remove violations that cannot be acted on by the remediator.

        Two categories are dropped:

        1. Sentinel file paths — the auditor could not resolve a real source
           file. These are project-scope or symbol-pair findings. The
           remediator cannot open "System" or "__symbol_pair__foo" as a file.

        2. Malformed rule IDs — the auditor returned an enforcement mapping
           file path as check_id (e.g. "enforcement/mappings/arch/foo.yaml").
           This is an auditor internal leaking into the finding. The remediator
           cannot map a file path to a fix strategy, and it creates misleading
           subjects on the blackboard.
        """
        actionable = []
        for v in violations:
            file_path = str(v.get("file_path") or "")
            rule_id = str(v.get("rule_id") or "")

            # Drop sentinel file paths
            if file_path in _SENTINEL_FILE_PATHS:
                logger.debug(
                    "AuditViolationSensor: dropping sentinel file_path=%r rule=%r",
                    file_path,
                    rule_id,
                )
                continue

            if file_path.startswith("__symbol_pair__"):
                logger.debug(
                    "AuditViolationSensor: dropping symbol-pair file_path=%r rule=%r",
                    file_path,
                    rule_id,
                )
                continue

            # Drop findings where the file path is not a Python source file
            if not file_path.endswith(".py"):
                logger.debug(
                    "AuditViolationSensor: dropping non-Python file_path=%r rule=%r",
                    file_path,
                    rule_id,
                )
                continue

            # Drop malformed rule IDs — file paths leaked from the auditor engine.
            # A real rule ID never contains "/" (e.g. "purity.no_dead_code").
            # Enforcement mapping paths do (e.g. "enforcement/mappings/arch/foo.yaml").
            if "/" in rule_id:
                logger.debug(
                    "AuditViolationSensor: dropping malformed rule_id=%r file=%r",
                    rule_id,
                    file_path,
                )
                continue

            actionable.append(v)

        return actionable

    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Query the blackboard for all already-posted subjects matching this
        sensor's namespace prefix, regardless of which worker posted them.

        Intentionally does NOT filter by worker_uuid. Deduplication must be
        by subject content, not by poster identity. This prevents different
        daemon generations or parallel sensor instances from re-posting the
        same violation when their UUIDs differ.
        """
        prefix = f"{_FINDING_SUBJECT}::{self._rule_namespace}%"
        svc = await self._core_context.registry.get_blackboard_service()
        return await svc.fetch_open_finding_subjects_by_prefix(prefix)
