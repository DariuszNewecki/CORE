# src/mind/governance/rule_findings.py

"""Finding builders for the non-verdict outcomes of ``execute_rule``.

Split out of ``rule_executor`` (ADR-095 modularity finding) with no behavior
change: a missing engine, the llm_gate stub, a per-file engine crash, the
aggregated transient LLM failures and the files whose content could not be
evaluated. Mind layer: pure, no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.executable_rule import ExecutableRule


# ID: 1831aeef-8c7e-4c59-9293-3a3981e258db
def engine_missing_finding(rule: ExecutableRule, error: ValueError) -> AuditFinding:
    """BLOCK: the rule names an engine the registry does not know."""
    return AuditFinding(
        check_id=f"{rule.rule_id}.engine_missing",
        severity=AuditSeverity.BLOCK,
        message=str(error),
        file_path="none",
    )


# ID: ebae7117-f43c-4b58-a584-973d146a77f4
def llm_stub_finding(rule: ExecutableRule) -> AuditFinding:
    """#307: ONE WARNING for an llm_gate rule that fell back to the stub engine."""
    return AuditFinding(
        check_id=rule.rule_id,
        severity=AuditSeverity.HIGH,
        message=(
            f"Rule '{rule.rule_id}' uses engine '{rule.engine}' which "
            "is not operational in this run (no LLM client wired). "
            "Audit signal for this rule is muted until the wiring is "
            "available — see GitHub #306."
        ),
        file_path="none",
        context={
            "engine_id": rule.engine,
            "stub": True,
            "reason": "no_llm_client",
        },
    )


# ID: 1b49fe33-a539-4061-92f0-388c9e499f78
def enforcement_failure_finding(
    rule: ExecutableRule, file_path: object, rel_path: str, error: Exception
) -> AuditFinding:
    """HARDENING P0.1 (per-file): an engine crash on one file is a BLOCK
    ENFORCEMENT_FAILURE, never a pass."""
    return AuditFinding(
        check_id=f"{rule.rule_id}.enforcement_failure",
        severity=AuditSeverity.BLOCK,
        message=(
            f"ENFORCEMENT_FAILURE: Rule crashed on {file_path}: {error}. "
            f"Compliance status UNKNOWN — treat as non-compliant until fixed."
        ),
        file_path=rel_path,
        context={
            "finding_type": "ENFORCEMENT_FAILURE",
            "engine": rule.engine,
            "policy_id": rule.policy_id,
            "exception_type": type(error).__name__,
            "exception_message": str(error),
        },
    )


# ID: 5dd9c11f-543d-4b14-b5ab-287683950d7b
def transient_llm_failure_finding(
    rule: ExecutableRule, failures: list[tuple[str, str]]
) -> AuditFinding:
    """#306/#307: one aggregate WARNING for the transient LLM failures of a
    rule's run, given as (rel_path, underlying error) pairs.

    Bounds Blackboard pollution — the autonomous remediation loop sees one
    finding per affected rule instead of one per file. sample_files preserves
    enough signal for the governor to investigate without churning the loop.
    """
    # #309: deduplicate underlying error strings. A single root cause
    # (e.g. the prompt-contract mismatch that made #308 look transient)
    # shows up as one entry; a true intermittent shows many. Visible
    # from the message without reading every per-file sample.
    unique_errors = sorted({err for _, err in failures})
    return AuditFinding(
        check_id=rule.rule_id,
        severity=AuditSeverity.HIGH,
        message=(
            f"Rule '{rule.rule_id}' LLM evaluation failed transiently "
            f"on {len(failures)} file(s) "
            f"({len(unique_errors)} unique error(s)). Verdict for "
            "those files is UNKNOWN until the LLM provider can keep "
            "up with audit-scale throughput — see follow-up issue on "
            "llm_gate concurrency/batching."
        ),
        file_path="none",
        context={
            "finding_type": "LLM_TRANSIENT_FAILURE",
            "engine_id": rule.engine,
            "failure_count": len(failures),
            "sample_files": [path for path, _ in failures[:5]],
            "sample_errors": [
                {"file": path, "error": err} for path, err in failures[:5]
            ],
            "unique_error_messages": unique_errors[:5],
        },
    )


# ID: 7ae202d9-619e-4791-b733-cbdae90207e1
def content_not_evaluated_finding(
    rule: ExecutableRule, not_evaluated: list[tuple[str, str]]
) -> AuditFinding:
    """#1050: one INFO finding per rule for the files whose content it could
    not evaluate, given as (rel_path, reason) pairs. Not a failure: the rule
    did run, and its other checks (a naming pattern) still applied to them."""
    reasons = sorted({reason for _, reason in not_evaluated})
    return AuditFinding(
        check_id=f"{rule.rule_id}.content_not_evaluated",
        severity=AuditSeverity.INFO,
        message=(
            f"Rule '{rule.rule_id}' did not evaluate the content of "
            f"{len(not_evaluated)} file(s): {'; '.join(reasons)}."
        ),
        file_path="none",
        context={
            "finding_type": "CONTENT_NOT_EVALUATED",
            "engine": rule.engine,
            "policy_id": rule.policy_id,
            "file_count": len(not_evaluated),
            "sample_files": [path for path, _ in not_evaluated[:5]],
            "reasons": reasons,
        },
    )
