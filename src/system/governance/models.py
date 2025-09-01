# src/system/governance/models.py
"""
Data models for the Constitutional Auditor's audit findings and severity levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# CAPABILITY: system.audit.severity_level
class AuditSeverity(Enum):
    """Severity levels for audit findings."""

    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"


@dataclass
# CAPABILITY: system.audit.finding
class AuditFinding:
    """Represents a single audit finding."""

    severity: AuditSeverity
    message: str
    check_name: str
    file_path: Optional[str] = None
