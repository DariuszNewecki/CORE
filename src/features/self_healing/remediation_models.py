# src/features/self_healing/remediation_models.py
"""
Data models for the Audit Remediation Service.

These are the "boxes" we use to organize information as it flows through
the remediation process:
  - What patterns matched
  - What fixes we tried
  - What the results were

Think of these as forms you fill out to keep track of what happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from features.autonomy.audit_analyzer import AutoFixablePattern
from shared.models import AuditFinding


# ==============================================================================
# ENUMS - These are like multiple choice options
# ==============================================================================


# ID: 6d502541-a127-4c4c-9d1b-cb269ef5f527
class RemediationMode(Enum):
    """
    How aggressive should we be when fixing things?

    SAFE_ONLY = Only fix things we're very confident about (>85% sure, low risk)
    MEDIUM_RISK = Include fixes that are pretty safe (>70% sure, low-medium risk)
    ALL_DETERMINISTIC = Try all fixes that don't involve AI reasoning

    Start with SAFE_ONLY. Only use others when you trust the system.
    """

    SAFE_ONLY = "safe_only"
    MEDIUM_RISK = "medium_risk"
    ALL_DETERMINISTIC = "all_deterministic"


# ==============================================================================
# MATCH RECORDS - Tracking when a finding matches a fix pattern
# ==============================================================================


@dataclass
# ID: 5ffc4890-959e-4a45-8bd2-cef113dccede
class MatchedPattern:
    """
    Records when an audit finding matches a pattern we know how to fix.

    Example:
        Finding: "Imports are not sorted in file X"
        Pattern: "I know how to sort imports"
        Result: MatchedPattern connecting them

    This is evidence for later - we can see which patterns matched which problems.
    """

    finding: AuditFinding  # The problem we found
    pattern: AutoFixablePattern  # The fix pattern that applies
    confidence: float  # How confident we are (0.0 to 1.0)
    risk_level: str  # "low", "medium", or "high"


# ==============================================================================
# FIX EXECUTION RECORDS - What happened when we tried to fix something
# ==============================================================================


@dataclass
# ID: 7d298182-0eee-430d-a9ff-c6a26d7e6460
class FixResult:
    """
    The outcome of trying to apply ONE fix.

    This is what a fix handler returns to tell us:
    - Did it work? (ok = True/False)
    - If not, what went wrong? (error_message)
    - Any extra details? (changes_made)

    Example:
        FixResult(
            ok=True,
            error_message=None,
            changes_made={"imports_sorted": 15}
        )
    """

    ok: bool  # Did the fix work?
    error_message: str | None = None  # If not, why not?
    changes_made: dict[str, Any] | None = None  # Optional details about what changed


@dataclass
# ID: f3ea5a75-ed5d-4f01-8fd7-3a1cc7bce259
class FixDetail:
    """
    Complete record of a single fix attempt - for evidence trail.

    After we try to fix something, we create one of these to remember:
    - Which file we fixed
    - Which fix handler we used
    - Whether it worked
    - How long it took

    These get saved in the evidence file so we can review what happened.
    """

    finding_id: str  # Unique identifier for the finding we fixed
    file_path: str  # Which file we modified
    action_handler: str  # Which handler function we used (e.g., "sort_imports")
    status: str  # "success", "failed", or "skipped"
    error_message: str | None  # If it failed, why?
    duration_ms: int  # How long it took in milliseconds


# ==============================================================================
# OVERALL RESULTS - The complete story of a remediation session
# ==============================================================================


@dataclass
# ID: cfc0238c-1276-4fa7-8373-41d969175a9d
class RemediationResult:
    """
    The complete report of one remediation run.

    This is the "big picture" summary that tells you:
    - How many problems we started with
    - How many we could fix
    - How many we actually fixed successfully
    - Whether things got better

    Gets saved as JSON evidence file for full traceability.
    """

    # Identity - when did this happen?
    session_id: str  # Unique ID for this run (UUID)
    timestamp_utc: str  # When it happened (ISO format)

    # Input stats - what we started with
    total_findings: int  # Total problems from audit
    findings_by_severity: dict[str, int]  # How many ERROR, WARNING, INFO

    # Matching results - what we could potentially fix
    matched_patterns: list[MatchedPattern]  # Problems that matched fix patterns
    unmatched_findings: list[AuditFinding]  # Problems we don't know how to fix yet

    # Execution results - what we actually did
    fixes_attempted: int  # How many fixes we tried
    fixes_succeeded: int  # How many worked
    fixes_failed: int  # How many didn't work

    # Validation - did we make things better?
    validation_passed: bool  # True if audit shows improvement
    findings_before: int  # Violation count before fixes
    findings_after: int  # Violation count after fixes
    improvement_delta: int  # How many fewer violations (positive = good)

    # Evidence trail - details for review
    fix_details: list[FixDetail]  # Complete list of what we tried
    duration_sec: float  # Total time elapsed

    # File references - where to find related files
    audit_input_path: str  # Where we read audit findings from
    remediation_output_path: str  # Where we wrote this result to
    validation_audit_path: str | None = None  # Where validation audit was saved


# ==============================================================================
# HELPER FUNCTIONS - Making it easier to create these objects
# ==============================================================================


# ID: bcd21dff-5338-4754-baaf-30106517b102
def create_remediation_result(
    total_findings: int,
    findings_by_severity: dict[str, int],
    matched_patterns: list[MatchedPattern],
    unmatched_findings: list[AuditFinding],
    fix_details: list[FixDetail],
    findings_before: int,
    findings_after: int,
    audit_input_path: str,
    remediation_output_path: str,
    validation_audit_path: str | None,
    duration_sec: float,
) -> RemediationResult:
    """
    Helper function to create a RemediationResult with less typing.

    This automatically:
    - Generates a unique session ID
    - Sets the current timestamp
    - Calculates success/failure counts
    - Determines if validation passed

    You just need to provide the actual data.
    """

    # Generate unique ID for this session
    import uuid

    session_id = str(uuid.uuid4())

    # Get current time in ISO format
    timestamp_utc = datetime.now(UTC).isoformat()

    # Count successes and failures
    fixes_succeeded = sum(1 for detail in fix_details if detail.status == "success")
    fixes_failed = sum(1 for detail in fix_details if detail.status == "failed")
    fixes_attempted = fixes_succeeded + fixes_failed

    # Calculate improvement
    improvement_delta = findings_before - findings_after
    validation_passed = improvement_delta > 0  # We must show improvement

    return RemediationResult(
        session_id=session_id,
        timestamp_utc=timestamp_utc,
        total_findings=total_findings,
        findings_by_severity=findings_by_severity,
        matched_patterns=matched_patterns,
        unmatched_findings=unmatched_findings,
        fixes_attempted=fixes_attempted,
        fixes_succeeded=fixes_succeeded,
        fixes_failed=fixes_failed,
        validation_passed=validation_passed,
        findings_before=findings_before,
        findings_after=findings_after,
        improvement_delta=improvement_delta,
        fix_details=fix_details,
        duration_sec=duration_sec,
        audit_input_path=audit_input_path,
        remediation_output_path=remediation_output_path,
        validation_audit_path=validation_audit_path,
    )
