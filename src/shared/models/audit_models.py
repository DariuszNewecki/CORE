# src/shared/models/audit_models.py
"""
Defines the Pydantic models for representing the results of a constitutional audit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum  # <-- CHANGED from Enum to IntEnum
from typing import Any, Dict, Optional


# ID: 5ccdae76-2214-413d-8551-13d4b224b694
class AuditSeverity(IntEnum):  # <-- CHANGED from Enum to IntEnum
    """Enumeration for the severity of an audit finding."""

    INFO = 1
    WARNING = 2
    ERROR = 3

    # This allows us to use severity.name in lowercase, e.g., 'info'
    def __str__(self):
        return self.name.lower()

    @property
    # ID: bad8d002-de4c-4b09-900f-0cd784c60242
    def is_blocking(self) -> bool:
        """Returns True if the severity level should block a CI/CD pipeline."""
        return self == AuditSeverity.ERROR


@dataclass
# ID: 1bc3d2f1-466b-49b9-aacd-6fac9e03a068
class AuditFinding:
    """Represents a single finding from a constitutional audit check."""

    check_id: str
    severity: AuditSeverity
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    # ID: d638215e-ceb0-421e-b33b-a0b191876530
    def as_dict(self) -> Dict[str, Any]:
        """Serializes the finding to a dictionary for reporting."""
        return {
            "check_id": self.check_id,
            "severity": str(self.severity),
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
        }
