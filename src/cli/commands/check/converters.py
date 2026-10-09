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


# ID: cfb45511-cfe2-42c6-994e-6a618dd16104
def severity_from_string(value: str | None) -> AuditSeverity:
    """Convert lowercase string severity to enum, defaulting to BLOCK."""
    if not value:
        return AuditSeverity.BLOCK
    v = value.strip().lower()
    try:
        return AuditSeverity[v.upper()]
    except KeyError:
        return AuditSeverity.BLOCK
