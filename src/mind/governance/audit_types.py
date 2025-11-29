# src/mind/governance/audit_types.py
"""
Types and metadata for the audit subsystem.

- AuditCheckMetadata: optional metadata for each check
- AuditCheckResult: normalized result shape for reporting
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.models import AuditFinding, AuditSeverity


@dataclass(frozen=True)
# ID: 8e683f4c-de46-40fd-85ef-4f04093aadd3
class AuditCheckMetadata:
    """
    Optional metadata for an audit check.

    Attach this as `metadata` on a BaseCheck subclass to influence
    how it is displayed in reports and summaries.

    Example:

        class ImportGroupCheck(BaseCheck):
            metadata = AuditCheckMetadata(
                id="import_group",
                name="Import Grouping",
                category="style",
                fix_hint="core-admin fix.import-groups",
                default_severity=AuditSeverity.LOW,
            )
    """

    id: str
    name: str
    category: str | None = None
    fix_hint: str | None = None
    default_severity: AuditSeverity | None = None


@dataclass
# ID: c4583c77-b87e-4196-a63c-1bbcee63fc3a
class AuditCheckResult:
    """
    Normalized result for a single audit check, produced by the audit runner
    and consumed by the AuditRunReporter.
    """

    name: str
    category: str | None
    duration_sec: float
    findings_count: int
    max_severity: AuditSeverity | None
    fix_hint: str | None
    extra: dict[str, Any] | None = None

    @property
    # ID: a366d4bd-d741-433e-b7e6-b14e275793a0
    def has_issues(self) -> bool:
        """Return True if this check produced any findings."""
        return self.findings_count > 0

    @classmethod
    # ID: c36a9fd6-438e-49fe-b2f3-78489bdec0e0
    def from_raw(
        cls,
        check_cls: type,
        findings: list[AuditFinding],
        duration_sec: float,
    ) -> AuditCheckResult:
        """
        Helper to build a result from a check class + findings.
        Uses AuditCheckMetadata if present to enrich the result.
        """

        meta: AuditCheckMetadata | None = getattr(check_cls, "metadata", None)

        name = meta.name if meta and meta.name else check_cls.__name__
        category = meta.category if meta else None
        fix_hint = meta.fix_hint if meta else None

        findings_count = len(findings)
        max_severity: AuditSeverity | None = None
        if findings:
            max_severity = max((f.severity for f in findings), default=None)

        return cls(
            name=name,
            category=category,
            duration_sec=duration_sec,
            findings_count=findings_count,
            max_severity=max_severity,
            fix_hint=fix_hint,
        )
