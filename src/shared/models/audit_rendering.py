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
        AuditSeverity.ERROR: "bold red",
        AuditSeverity.WARNING: "bold yellow",
        AuditSeverity.INFO: "cyan",
    }.get(severity, "white")
