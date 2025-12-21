# src/mind/governance/enforcement_methods.py
# ID: model.mind.governance.enforcement_methods
"""
Enforcement method base classes for constitutional rule verification.

Provides composable enforcement strategies that can be declared in checks
rather than implementing custom verification logic each time.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: enforcement-method-base
# ID: 89954e85-77c2-46f2-943c-fb974126aa7e
class EnforcementMethod(ABC):
    """
    Base class for enforcement verification strategies.
    Each method answers: "Is this rule actually enforced?"
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        self.rule_id = rule_id
        self.severity = severity

    @abstractmethod
    # ID: 8704b7ad-e6b5-4e77-8846-ed6358ba0767
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Verify that enforcement exists for this rule.
        Returns findings if enforcement is missing or incorrect.
        """
        pass

    def _create_finding(
        self,
        message: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> AuditFinding:
        """Helper to create standardized findings."""
        return AuditFinding(
            check_id=self.rule_id,
            severity=self.severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
        )


# ID: path-protection-enforcement
# ID: db3c250e-b770-4e71-9f84-03b6df1da7c8
class PathProtectionEnforcement(EnforcementMethod):
    """
    Verifies that protected paths are enforced by IntentGuard.
    Used for immutability rules like safety.charter_immutable.
    """

    def __init__(
        self,
        rule_id: str,
        expected_patterns: list[str] | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.expected_patterns = expected_patterns or []

    # ID: dcd85ecd-cad7-4b12-93a9-e65cb6f3eea8
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        # 1. Check SSOT: Rule declares protected_paths
        protected_paths = rule_data.get("protected_paths", [])
        if not protected_paths:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare 'protected_paths' for path protection enforcement.",
                    file_path="N/A",
                )
            )
            return findings

        # 2. Verify expected patterns if specified
        if self.expected_patterns:
            for pattern in self.expected_patterns:
                if pattern not in protected_paths:
                    findings.append(
                        self._create_finding(
                            f"Rule '{self.rule_id}' missing expected protected path: '{pattern}'",
                            file_path="N/A",
                        )
                    )

        # 3. Check runtime enforcement: IntentGuard should deny writes
        # TODO: Once IntentGuard loads protected_paths from SSOT, verify it here
        # For now, we just verify the declaration exists
        findings.append(
            self._create_finding(
                f"Rule '{self.rule_id}' declares protected paths but runtime enforcement not yet wired to IntentGuard.",
                file_path="N/A",
            )
        )

        return findings


# ID: code-pattern-enforcement
# ID: 245f2998-1a13-4c14-8e0f-da543417a63d
class CodePatternEnforcement(EnforcementMethod):
    """
    Verifies that code patterns are detected via AST scanning.
    Used for rules like safety.no_dangerous_execution.
    """

    def __init__(
        self,
        rule_id: str,
        required_patterns: list[str] | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.required_patterns = required_patterns or []

    # ID: 233c2300-922c-4fd7-8151-d890029399c8
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        # 1. Check SSOT: Rule declares detection method
        detection = rule_data.get("detection", {})
        if not detection:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare 'detection' method for code pattern enforcement.",
                    file_path="N/A",
                )
            )
            return findings

        method = detection.get("method")
        patterns = detection.get("patterns", [])

        if method != "ast_call_scan":
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' detection method must be 'ast_call_scan', got: '{method}'",
                    file_path="N/A",
                )
            )

        if not patterns:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare detection patterns.",
                    file_path="N/A",
                )
            )

        # 2. Verify required patterns if specified
        for required in self.required_patterns:
            if required not in patterns:
                findings.append(
                    self._create_finding(
                        f"Rule '{self.rule_id}' missing required pattern: '{required}'",
                        file_path="N/A",
                    )
                )

        # 3. Check runtime enforcement: Should have corresponding check
        # TODO: Verify AST scanner actually runs these patterns
        # For now, just verify the declaration

        return findings


# ID: audit-logging-enforcement
# ID: 3ba6198a-0a2e-4afe-ae3f-76a7c965fdf5
class AuditLoggingEnforcement(EnforcementMethod):
    """
    Verifies that actions are logged with required metadata.
    Used for transparency rules like safety.change_must_be_logged.
    """

    def __init__(
        self,
        rule_id: str,
        required_fields: list[str] | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.required_fields = required_fields or ["intent_bundle_id"]

    # ID: 190535e3-5261-4a8b-8756-ce3e49e0a83a
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        # 1. Check SSOT: Rule declares audit requirements
        enforcement = rule_data.get("enforcement")
        if enforcement != "error":
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must have 'enforcement: error' for audit logging.",
                    file_path="N/A",
                )
            )

        # 2. Verify audit metadata in Actions table
        # TODO: Query database to verify actions have required fields
        # For now, just flag as TODO
        findings.append(
            self._create_finding(
                f"Rule '{self.rule_id}' requires audit logging enforcement - database validation not yet implemented.",
                file_path="N/A",
            )
        )

        return findings


# ID: single-instance-enforcement
# ID: befdd49a-3cb9-4868-8480-9c7ba03ee61c
class SingleInstanceEnforcement(EnforcementMethod):
    """
    Verifies that exactly one instance of something exists.
    Used for rules like safety.single_active_constitution.
    """

    def __init__(
        self,
        rule_id: str,
        target_file: str,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.target_file = target_file

    # ID: 63493298-1e52-4555-92cf-b263ce4e4884
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        target_path = context.intent_path / self.target_file

        # 1. Verify target file exists
        if not target_path.exists():
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' requires '{self.target_file}' to exist.",
                    file_path=self.target_file,
                )
            )
            return findings

        # 2. Verify it references exactly one constitution
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


# ID: database-ssot-enforcement
# ID: ccf30541-e91a-42cb-afa0-8a3a3b3cf9c7
class DatabaseSSOTEnforcement(EnforcementMethod):
    """
    Verifies that data lives in database as SSOT.
    Used for rules like db.cli_registry_in_db.
    """

    def __init__(
        self,
        rule_id: str,
        table_name: str,
        deprecated_file: str | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        super().__init__(rule_id, severity)
        self.table_name = table_name
        self.deprecated_file = deprecated_file

    # ID: 95538fd4-7f21-429b-ba69-5cc3efe7e861
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        findings = []

        # 1. Check if deprecated file exists (should NOT)
        if self.deprecated_file:
            deprecated_path = context.intent_path / self.deprecated_file
            if deprecated_path.exists():
                findings.append(
                    self._create_finding(
                        f"Rule '{self.rule_id}' violated: '{self.deprecated_file}' should not exist (data must be in {self.table_name} table).",
                        file_path=self.deprecated_file,
                    )
                )

        # 2. Verify table has data
        # TODO: Query database to verify table exists and has records
        # For now, assume it exists if no deprecated file

        return findings
