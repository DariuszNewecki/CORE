# src/shared/models/audit_models.py
"""
Defines the Pydantic models for representing the results of a constitutional audit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


# ID: d9aa8c9a-3419-4995-8e84-6bdf16a7a76b
class AuditSeverity(Enum):
    """Enumeration for the severity of an audit finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    # ID: 3f9fe4ec-0727-48ac-9064-1e2096d516d3
    def is_blocking(self) -> bool:
        """Returns True if the severity level should block a CI/CD pipeline."""
        return self == AuditSeverity.ERROR


@dataclass
# ID: 020c2217-675f-4273-acea-6002560ffac3
class AuditFinding:
    """Represents a single finding from a constitutional audit check."""

    check_id: str
    severity: AuditSeverity
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    # ID: 0ca72d23-e3d2-4a0d-a071-db38d5c49332
    def as_dict(self) -> Dict[str, Any]:
        """Serializes the finding to a dictionary for reporting."""
        return {
            "check_id": self.check_id,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
        }
