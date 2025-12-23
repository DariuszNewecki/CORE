# src/shared/models/audit_models.py
"""
Defines the Pydantic models for representing the results of a constitutional audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


# ID: 5ccdae76-2214-413d-8551-13d4b224b694
class AuditSeverity(IntEnum):
    """Enumeration for the severity of an audit finding."""

    INFO = 1
    WARNING = 2
    ERROR = 3

    def __str__(self) -> str:
        # This allows us to use severity.name in lowercase, e.g., 'info'
        return self.name.lower()

    @property
    # ID: bad8d002-de4c-4b09-900f-0cd784c60242
    def is_blocking(self) -> bool:
        """Returns True if the severity level should block a CI/CD pipeline."""
        return self == AuditSeverity.ERROR


@dataclass(init=False)
# ID: 1bc3d2f1-466b-49b9-aacd-6fac9e03a068
class AuditFinding:
    """Represents a single finding from a constitutional audit check.

    Notes:
        - `context` is the single source of truth for structured finding data.
        - `details` is a backwards-compatible alias to `context`.
        - We accept `details=...` as an init kwarg for legacy callers without
          defining a dataclass field named `details` (avoids property collision).
    """

    check_id: str
    severity: AuditSeverity
    message: str
    file_path: str | None = None
    line_number: int | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        check_id: str,
        severity: AuditSeverity,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.check_id = check_id
        self.severity = severity
        self.message = message
        self.file_path = file_path
        self.line_number = line_number

        base_context: dict[str, Any] = dict(context or {})
        if details:
            base_context.update(details)

        self.context = base_context

    # ID: d638215e-ceb0-421e-b33b-a0b191876530
    def as_dict(self) -> dict[str, Any]:
        """Serializes the finding to a dictionary for reporting."""
        return {
            "check_id": self.check_id,
            "severity": str(self.severity),
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
            # Keep legacy key for consumers expecting "details"
            "details": self.context,
        }

    @property
    # ID: ed053380-56ba-4205-81d1-99e8550429f4
    def details(self) -> dict[str, Any]:
        """Backwards-compatible alias for structured finding context."""
        return self.context

    @details.setter
    # ID: f2ff68c6-7a4c-4cca-a7dc-4071d8b49c13
    def details(self, value: dict[str, Any] | None) -> None:
        self.context = value or {}
