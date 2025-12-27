# src/mind/governance/violation_report.py
"""
Violation reporting structures for constitutional enforcement.

Used by IntentGuard and engines to report policy violations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
# ID: eaac12b5-8310-469a-a89d-d6047e2fbc54
class ViolationReport:
    """
    Detailed violation report with remediation context.

    Attributes:
        rule_name: Rule identifier that was violated
        path: File path (repo-relative) where violation occurred
        message: Human-readable violation description
        severity: "error" or "warning"
        suggested_fix: Optional remediation guidance
        source_policy: Policy file that declared this rule
    """

    rule_name: str
    path: str
    message: str
    severity: str
    suggested_fix: str = ""
    source_policy: str = "unknown"


# ID: b0bc85fe-cc5b-4547-b2ae-cb6540e8df66
class ConstitutionalViolationError(Exception):
    """
    Raised when proposed changes violate constitutional policies.

    Used by IntentGuard to signal hard blocks (e.g., .intent writes).
    """

    pass
