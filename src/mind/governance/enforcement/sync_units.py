# src/mind/governance/enforcement/sync_units.py

"""Refactored logic for src/mind/governance/enforcement/sync_units.py."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.models import AuditFinding, AuditSeverity

from .base import EnforcementMethod


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


# ID: cdde2605-2b96-4135-8096-759bfc14ac41
# ID: db3c250e-b770-4e71-9f84-03b6df1da7c8
class PathProtectionEnforcement(EnforcementMethod):
    def __init__(
        self,
        rule_id: str,
        expected_patterns: list[str] | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.expected_patterns = expected_patterns or []

    # ID: 36531019-f1b4-4f8e-99e8-43baa6ee8bef
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []
        protected_paths = rule_data.get("protected_paths", [])
        if not protected_paths:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare 'protected_paths' for path protection enforcement.",
                    file_path="none",
                )
            )
            return findings
        if self.expected_patterns:
            for pattern in self.expected_patterns:
                if pattern not in protected_paths:
                    findings.append(
                        self._create_finding(
                            f"Rule '{self.rule_id}' missing expected protected path: '{pattern}'",
                            file_path="none",
                        )
                    )
        return findings


# ID: a4e18a5b-e598-4d1f-8a93-0f58900f6fdb
# ID: 245f2998-1a13-4c14-8e0f-da543417a63d
class CodePatternEnforcement(EnforcementMethod):
    def __init__(
        self,
        rule_id: str,
        required_patterns: list[str] | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.required_patterns = required_patterns or []

    # ID: 679c896e-67f4-4f1f-b079-78533536bcd4
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []
        detection = rule_data.get("detection", {})
        if not detection:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare 'detection' method for code pattern enforcement.",
                    file_path="none",
                )
            )
            return findings
        method = detection.get("method")
        patterns = detection.get("patterns", [])
        if method != "ast_call_scan":
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' detection method must be 'ast_call_scan', got: '{method}'",
                    file_path="none",
                )
            )
        if not patterns:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare detection patterns.",
                    file_path="none",
                )
            )
        for required in self.required_patterns:
            if required not in patterns:
                findings.append(
                    self._create_finding(
                        f"Rule '{self.rule_id}' missing required pattern: '{required}'",
                        file_path="none",
                    )
                )
        return findings


# ID: 1fec05a2-f2cb-4859-8b5a-a4a7f185a72c
# ID: befdd49a-3cb9-4868-8480-9c7ba03ee61c
class SingleInstanceEnforcement(EnforcementMethod):
    def __init__(
        self,
        rule_id: str,
        target_file: str,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.target_file = target_file

    # ID: e003a3a9-4c44-4756-8236-33b433d36d95
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []
        target_path = context.intent_path / self.target_file
        if not target_path.exists():
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' requires '{self.target_file}' to exist.",
                    file_path=self.target_file,
                )
            )
            return findings
        try:
            content = target_path.read_text().strip()
            lines = [
                line
                for line in content.splitlines()
                if line.strip() and not line.startswith("#")
            ]
            if len(lines) != 1:
                findings.append(
                    self._create_finding(
                        f"Rule '{self.rule_id}' requires exactly one active constitution reference, found {len(lines)}.",
                        file_path=self.target_file,
                    )
                )
        except Exception as e:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' failed to verify: {e}",
                    file_path=self.target_file,
                )
            )
        return findings
