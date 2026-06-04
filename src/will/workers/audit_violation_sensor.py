# src/will/workers/audit_violation_sensor.py
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

Cause attribution (ADR-015 D5):
- For each posted finding, the sensor consults ConsequenceLogService for the
  most recent proposal that touched the same file_path within a recency
  window. On match, the payload carries causing_proposal_id and
  causing_commit_sha; on no match, those keys are None and cause_attribution
  is the explicit string "untracked" (URS Q6 / issue #148 acceptance).

LAYER: will/workers — sensing worker. Receives CoreContext via constructor
injection. No file writes. No LLM. Pure perception. DB access is delegated
to Body services via the service registry — no direct session import.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker
from will.workers.audit_violation_filter import filter_actionable_violations
from will.workers.audit_violation_normalizer import normalize_audit_findings


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

        # ADR-039: refresh governance and filesystem inputs before
        # resolving rules so content committed since the previous cycle
        # is visible without daemon restart.
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        intent_repo = get_intent_repository()

        auditor_context = self._core_context.auditor_context
        auditor_context.reload_governance()
        auditor_context.invalidate_file_cache()

        # F-41 ADR-090 Phase 2: discovery globs come from the python artifact
        # type declaration in the registry, not an implicit rglob("*.py").
        # Findings themselves still come from the auditor whose scope is its
        # own config — this log-line migration is the smallest Phase-2 step
        # that proves registry consumption without changing audit behavior.
        # F-42 (#416) will replace the hardcoded "python" lookup with the
        # artifact_type named on the sensor's worker declaration.
        python_globs = intent_repo.get_artifact_type("python").content["discovery"]
        file_count = sum(
            1
            for pattern in python_globs
            for _ in auditor_context.repo_path.glob(pattern)
        )
        rule_count = len(intent_repo._rule_index or {})
        logger.info(
            "audit_sensor_%s: rescanned %d files, %d rules loaded",
            self._rule_namespace,
            file_count,
            rule_count,
        )

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

        raw_violations = await normalize_audit_findings(
            self._core_context, self._rule_namespace, rule_ids
        )
        violations = filter_actionable_violations(raw_violations)

        filtered_out = len(raw_violations) - len(violations)
        if filtered_out:
            logger.info(
                "AuditViolationSensor[%s]: filtered %d unactionable violations "
                "(sentinel file paths or malformed rule IDs).",
                self._rule_namespace,
                filtered_out,
            )

        # ADR-045: drain the awaiting_reaudit queue for this namespace.
        # Subjects of currently-detected violations are the authoritative
        # set; quarantined findings whose subject is present are released
        # to 'open', the rest are resolved with system.audit attribution.
        # Runs after the audit produced this cycle's truth so we can
        # adjudicate without a second evaluation pass.
        current_subjects = {
            f"{_FINDING_SUBJECT}::{v.get('rule_id', self._rule_namespace)}::{v['file_path']}"
            for v in violations
        }
        bb_svc = await self._core_context.registry.get_blackboard_service()
        reaudit = await bb_svc.adjudicate_awaiting_reaudit_findings(
            subject_prefix=f"audit.violation::{self._rule_namespace}",
            current_violation_subjects=current_subjects,
            resolved_by="audit_violation_sensor",
        )
        reaudit_released = len(reaudit["released_subjects"])
        reaudit_resolved = len(reaudit["resolved_subjects"])
        if reaudit_released or reaudit_resolved:
            logger.info(
                "AuditViolationSensor[%s]: reaudit drained %d released, %d resolved.",
                self._rule_namespace,
                reaudit_released,
                reaudit_resolved,
            )
            await self.post_report(
                subject=f"audit.reaudit.complete::{self._rule_namespace}",
                payload={
                    "rule_namespace": self._rule_namespace,
                    "released_count": reaudit_released,
                    "resolved_count": reaudit_resolved,
                    "released_subjects": reaudit["released_subjects"],
                    "resolved_subjects": reaudit["resolved_subjects"],
                },
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
            svc = await self._core_context.registry.get_blackboard_service()
            expired = await svc.resolve_dry_run_entries_for_namespace(
                self._rule_namespace
            )
            if expired:
                logger.info(
                    "AuditViolationSensor[%s]: expired %d stale dry-run entries "
                    "(no violations found this cycle).",
                    self._rule_namespace,
                    expired,
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

        # ADR-015 D5: heuristic cause attribution via Body's ConsequenceLogService.
        # Resolved once before the loop; lookback is sensor-config-tunable.
        consequence_svc = (
            await self._core_context.registry.get_consequence_log_service()
        )
        lookback = getattr(self, "_config", {}).get("cause_lookback_seconds", 3600)

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

            cause = await consequence_svc.find_cause_for_file(
                v["file_path"], lookback_seconds=lookback
            )

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
                    "causing_proposal_id": cause["causing_proposal_id"],
                    "causing_commit_sha": cause["causing_commit_sha"],
                    "cause_attribution": (
                        "heuristic" if cause["causing_proposal_id"] else "untracked"
                    ),
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

    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Query the blackboard for all already-posted subjects matching this
        sensor's namespace prefix, regardless of which worker posted them.

        A finding is considered a duplicate if a blackboard entry with the same
        subject exists in any status except resolved. This includes abandoned
        entries — preventing sensors from re-posting violations that were
        processed and abandoned on the same cycle.

        Intentionally does NOT filter by worker_uuid. Deduplication must be
        by subject content, not by poster identity. This prevents different
        daemon generations or parallel sensor instances from re-posting the
        same violation when their UUIDs differ.
        """
        prefix = f"{_FINDING_SUBJECT}::{self._rule_namespace}%"
        svc = await self._core_context.registry.get_blackboard_service()
        return await svc.fetch_active_finding_subjects_by_prefix(prefix)
