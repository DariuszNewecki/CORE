# src/system/governance/models.py
"""
Data models for the Constitutional Auditor's audit findings and severity levels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AuditSeverity(Enum):
    """Severity levels for audit findings."""

    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"


@dataclass
class AuditFinding:
    """Represents a single audit finding."""

    severity: AuditSeverity
    message: str
    check_name: str
    file_path: Optional[str] = None
