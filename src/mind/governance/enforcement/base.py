# src/mind/governance/enforcement/base.py

"""Refactored logic for src/mind/governance/enforcement/base.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


# ID: 2b81c04c-5214-4228-ac9c-c1a7c22abdf2
# ID: 3e1f2a3b-4c5d-6e7f-8a9b-0c1d2e3f4a5b
class RuleEnforcementCheck(ABC):
    """
    Base class for orchestrating one or more enforcement methods.
    """

    policy_rule_ids: ClassVar[list[str]] = []
    policy_file: ClassVar[Path | None] = None
    enforcement_methods: ClassVar[list[EnforcementMethod | AsyncEnforcementMethod]] = []

    @property
    @abstractmethod
    def _is_concrete_check(self) -> bool:
        """Enforces that only leaf implementations are used."""
        pass


# ID: 39c7cbb0-d06e-4f83-a04e-636831a614a0
# ID: 89954e85-77c2-46f2-943c-fb974126aa7e
class EnforcementMethod(ABC):
    """Base class for SYNCHRONOUS enforcement verification strategies."""

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        self.rule_id = rule_id
        self.severity = severity

    @abstractmethod
    # ID: fe8bc0f5-a6be-4757-b68d-b713a8308c2d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        pass

    def _create_finding(
        self, message: str, file_path: str | None = None, line_number: int | None = None
    ) -> AuditFinding:
        """Helper to create standardized findings."""
        return AuditFinding(
            check_id=self.rule_id,
            severity=self.severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
        )


# ID: 58f327bd-6888-46d7-b1e4-206498424c01
# ID: 7f3a2b91-8c4d-5e6f-9a0b-1c2d3e4f5a6b
class AsyncEnforcementMethod(ABC):
    """Base class for ASYNCHRONOUS enforcement verification strategies."""

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        self.rule_id = rule_id
        self.severity = severity

    @abstractmethod
    # ID: de3d23e0-0da8-4da4-9990-dcabb6c76e25
    async def verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        pass

    def _create_finding(
        self, message: str, file_path: str | None = None, line_number: int | None = None
    ) -> AuditFinding:
        """Helper to create standardized findings."""
        return AuditFinding(
            check_id=self.rule_id,
            severity=self.severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
        )
