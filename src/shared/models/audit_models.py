# src/shared/models/audit_models.py
"""
Defines the Pydantic models for representing the results of a constitutional audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


# ID: 3f9b1d52-8a4e-4c17-b0d6-2e7f9a4c1b83
class EvidenceClass(str, Enum):
    """How a finding's verdict was established (ADR-113).

    Orthogonal to ``AuditSeverity`` (how *bad* the gap is): this records how
    the verdict was *reached*, which is the honesty surface CORE's GRC
    gap-analysis is sold on. Stored as its lowercase string value.

    - ``proven``   — established by a deterministic method (presence, pattern,
      structure, date arithmetic). Reproducible; no judgment.
    - ``judged``   — established by an AI/semantic reading. An opinion, labelled
      as one — never a fact.
    - ``attested`` — cannot be established automatically; a human must decide.
      Also the fail-closed default: an undeclared engine, a crashed check, or a
      muted check degrades to ``attested`` (never to a false ``proven``), per
      ADR-113 D3. Absence of a claim is never read as the strongest claim.
    """

    PROVEN = "proven"
    JUDGED = "judged"
    ATTESTED = "attested"

    def __str__(self) -> str:
        return self.value


# ID: 5ccdae76-2214-413d-8551-13d4b224b694
class AuditSeverity(IntEnum):
    """Enumeration for the severity of an audit finding.

    Five-value scale (ADR-059 D2): INFO/LOW/MEDIUM/HIGH/BLOCK. Stored as
    lowercase string via __str__. BLOCK is the sole CI-blocking severity;
    HIGH/MEDIUM/LOW are actionable at decreasing urgency; INFO is
    informational only. Governed by `audit_severity` in
    .intent/META/enums.json.
    """

    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    BLOCK = 5

    def __str__(self) -> str:
        # This allows us to use severity.name in lowercase, e.g., 'info'
        return self.name.lower()

    @property
    # ID: bad8d002-de4c-4b09-900f-0cd784c60242
    def is_blocking(self) -> bool:
        """Returns True if the severity level should block a CI/CD pipeline."""
        return self == AuditSeverity.BLOCK


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
    # ADR-113: how this verdict was established. Fail-closed default is
    # ATTESTED ("unknown / needs a human") — never a false PROVEN. The
    # rule_executor overwrites this with the producing engine's declared
    # class for genuine verdicts; crash/unknown findings keep the default.
    evidence_class: EvidenceClass = EvidenceClass.ATTESTED

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
        evidence_class: EvidenceClass = EvidenceClass.ATTESTED,
    ) -> None:
        self.check_id = check_id
        self.severity = severity
        self.message = message
        self.file_path = file_path
        self.line_number = line_number
        self.evidence_class = evidence_class

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
            "evidence_class": str(self.evidence_class),  # ADR-113
            "message": self.message,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "context": self.context,
            # Keep the "details" key for existing consumers
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
