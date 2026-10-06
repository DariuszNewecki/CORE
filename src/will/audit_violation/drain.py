# src/will/audit_violation/drain.py
"""
Clean-pass drains for AuditViolationSensor.

After a cycle's audit has produced the authoritative set of current
violations, three quarantine-style queues for the sensor's namespace are
adjudicated against it:

1. ``awaiting_reaudit`` (ADR-045) — present subjects are released to
   ``open``, absent ones resolved with system.audit attribution.
2. ``indeterminate`` (ADR-127) — findings whose violation has cleared are
   resolved; those still holding are left untouched.
3. Type-B ``abandoned`` (ADR-127 D7) — same clean-pass resolution.

The helper only adjudicates and builds the report payload. The sensor posts
its own blackboard report — helpers never post to the blackboard.

LAYER: will/workers — collaborator of AuditViolationSensor. Receives the
blackboard service by injection; no direct session import, no file writes.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f6c7e38a-52d5-4565-b259-a9c989ee922f
async def drain_cleared_findings(
    bb_svc: Any,
    *,
    artifact_type_id: str,
    rule_namespace: str,
    current_violations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Run the reaudit / indeterminate / abandoned drains for one namespace.

    Returns the ``audit.reaudit.complete`` report payload when any drain moved
    a finding, else None. The caller posts the report.
    """
    # ADR-045: drain the awaiting_reaudit queue for this namespace.
    # Subjects of currently-detected violations are the authoritative
    # set; quarantined findings whose subject is present are released
    # to 'open', the rest are resolved with system.audit attribution.
    # Runs after the audit produced this cycle's truth so we can
    # adjudicate without a second evaluation pass.
    #
    # ADR-091 D2 canonical subject format applies: subjects emitted by
    # this sensor are `<artifact_type>::<rule_id>::<file_path>` and the
    # reaudit drain scopes by `<artifact_type>::<rule_namespace>`.
    # Delegated violations still hold, so they count as current: otherwise
    # the indeterminate drain below would resolve each delegated finding
    # the cycle after it was escalated, and the sensor would re-post it.
    current_subjects = {
        f"{artifact_type_id}::{v.get('rule_id', rule_namespace)}::{v['file_path']}"
        for v in current_violations
    }
    reaudit = await bb_svc.adjudicate_awaiting_reaudit_findings(
        subject_prefix=f"{artifact_type_id}::{rule_namespace}",
        current_violation_subjects=current_subjects,
        resolved_by="audit_violation_sensor",
    )
    reaudit_released = len(reaudit["released_subjects"])
    reaudit_resolved = len(reaudit["resolved_subjects"])

    # ADR-127: drain indeterminate findings whose violations have cleared.
    # Symmetrical to the awaiting_reaudit drain above but targets
    # 'indeterminate' status. Findings whose violation still holds are left
    # untouched — the remediation-uncertainty judgment remains valid.
    # Findings whose violation is gone are resolved (system.audit authority).
    indet = await bb_svc.adjudicate_indeterminate_findings(
        subject_prefix=f"{artifact_type_id}::{rule_namespace}",
        current_violation_subjects=current_subjects,
        resolved_by="audit_violation_sensor",
    )
    indet_resolved = len(indet["resolved_subjects"])

    # ADR-127 D7: drain Type-B 'abandoned' findings whose violations have
    # cleared. Symmetrical to the indeterminate drain above. Reaches only
    # Type-B (ViolationExecutorWorker's remediation-attempt-cap abandons,
    # ADR-104 D9) — never Type-A telemetry (worker.silent, loop_hold.sample,
    # ...), which never matches this subject_prefix by construction. See
    # ADR-127 addendum D7.
    aband = await bb_svc.adjudicate_abandoned_findings(
        subject_prefix=f"{artifact_type_id}::{rule_namespace}",
        current_violation_subjects=current_subjects,
        resolved_by="audit_violation_sensor",
    )
    aband_resolved = len(aband["resolved_subjects"])

    if not (reaudit_released or reaudit_resolved or indet_resolved or aband_resolved):
        return None

    return {
        "rule_namespace": rule_namespace,
        "released_count": reaudit_released,
        "resolved_count": reaudit_resolved,
        "released_subjects": reaudit["released_subjects"],
        "resolved_subjects": reaudit["resolved_subjects"],
        "indeterminate_drained": indet_resolved,
        "indeterminate_drain_subjects": indet["resolved_subjects"],
        "abandoned_drained": aband_resolved,
        "abandoned_drain_subjects": aband["resolved_subjects"],
    }
