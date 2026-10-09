# src/cli/commands/check/converters.py
"""
Data converters for audit results.

Handles conversion between different audit finding formats:
- Engine findings (dicts) -> AuditFinding objects
- String severities -> AuditSeverity enums
- File path resolution
"""

from __future__ import annotations

import typer

from shared.models import AuditSeverity


# ID: f9bbf525-5d2f-4c77-aba6-5b30e81de71b
def parse_min_severity(severity: str) -> AuditSeverity:
    """Parse severity string to AuditSeverity enum with validation."""
    try:
        return AuditSeverity[severity.upper()]
    except KeyError as exc:
        raise typer.BadParameter(
            f"Invalid severity level '{severity}'. "
            f"Must be one of: info, low, medium, high, block."
        ) from exc
