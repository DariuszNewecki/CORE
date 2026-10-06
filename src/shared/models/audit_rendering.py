# src/shared/models/audit_rendering.py
"""Data models and utilities for audit rendering."""

from dataclasses import dataclass

from shared.models import AuditFinding, AuditSeverity


@dataclass(frozen=True)
# ID: 94bf6a41-7736-4851-a138-c863f00c24a9
class SeverityGroup:
    """Immutable group of findings by severity."""

    severity: AuditSeverity
    findings: tuple[AuditFinding, ...]

    @property
    # ID: 68064f46-680f-4c86-b7e3-8fd054e56b97
    def count(self) -> int:
        return len(self.findings)


# ID: 8d6c0049-4f2f-4102-829a-486e084b6bab
def get_severity_style(severity: AuditSeverity) -> str:
    """Get Rich console style string for a severity level."""
    return {
        AuditSeverity.BLOCK: "bold red",
        AuditSeverity.HIGH: "bold yellow",
        AuditSeverity.INFO: "cyan",
    }.get(severity, "white")


# #956: findings that record a check which could not run (ADR-005 §3,
# #847/#856). They carry the rule's severity for the verdict machinery, but
# they assert no violation, so presentation must not show them as one.
NOT_EVALUATED_FINDING_TYPES = frozenset(
    {"ENFORCEMENT_UNAVAILABLE", "ENFORCEMENT_FAILURE"}
)


# ID: 1aece734-6bf6-40d9-877c-45628a8ea8da
def is_not_evaluated(finding: AuditFinding) -> bool:
    """True when the finding records a check that could not be evaluated."""
    context = finding.context if isinstance(finding.context, dict) else {}
    return context.get("finding_type") in NOT_EVALUATED_FINDING_TYPES
