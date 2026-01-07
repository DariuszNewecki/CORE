# src/mind/governance/enforcement_methods.py
# ID: model.mind.governance.enforcement_methods
"""
Enforcement method base classes for constitutional rule verification.

Provides composable enforcement strategies that can be declared in checks
rather than implementing custom verification logic each time.

ARCHITECTURAL DESIGN:
- EnforcementMethod: Sync interface for file/AST-based checks
- AsyncEnforcementMethod: Async interface for DB/network-based checks
- RuleEnforcementCheck: Orchestrator for multiple enforcement methods

This separation follows the Big Boys principle: don't force async into sync.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: rule-enforcement-check-base
# ID: 3e1f2a3b-4c5d-6e7f-8a9b-0c1d2e3f4a5b
class RuleEnforcementCheck(ABC):
    """
    Base class for orchestrating one or more enforcement methods.

    This allows a single rule to be verified by multiple methods
    (e.g., checking both filesystem state and database consistency).
    """

    policy_rule_ids: ClassVar[list[str]] = []
    policy_file: ClassVar[Path | None] = None
    enforcement_methods: ClassVar[list[EnforcementMethod | AsyncEnforcementMethod]] = []

    @property
    @abstractmethod
    def _is_concrete_check(self) -> bool:
        """Enforces that only leaf implementations are used."""
        pass


# ID: enforcement-method-base
# ID: 89954e85-77c2-46f2-943c-fb974126aa7e
class EnforcementMethod(ABC):
    """
    Base class for SYNCHRONOUS enforcement verification strategies.

    Use this for checks that operate on:
    - Filesystem artifacts (.intent/ files, source code)
    - AST parsing (code structure analysis)
    - Static configuration (YAML/JSON validation)

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

        SYNC ONLY: Do not perform async operations (DB queries, network calls).
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


# ID: async-enforcement-method-base
# ID: 7f3a2b91-8c4d-5e6f-9a0b-1c2d3e4f5a6b
class AsyncEnforcementMethod(ABC):
    """
    Base class for ASYNCHRONOUS enforcement verification strategies.

    Use this for checks that operate on:
    - Database queries (SSOT validation)
    - Network calls (external service checks)
    - Any async I/O operations

    CONSTITUTIONAL ALIGNMENT:
    - Does NOT hijack event loops (awaits properly)
    - Assumes caller provides async context
    - Follows Database-as-SSOT principle
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        self.rule_id = rule_id
        self.severity = severity

    @abstractmethod
    # ID: 8a4b5c6d-7e8f-9a0b-1c2d3e4f5a6b
    # ID: b460b746-d24e-4b8b-8a9f-cc427dccaf5a
    async def verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Verify that enforcement exists for this rule (async).
        Returns findings if enforcement is missing or incorrect.

        ASSUMES: Caller has already established async context (event loop running).
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


# ============================================================================
# SYNCHRONOUS ENFORCEMENT METHODS (Filesystem/AST-based)
# ============================================================================


# ID: path-protection-enforcement
# ID: db3c250e-b770-4e71-9f84-03b6df1da7c8
class PathProtectionEnforcement(EnforcementMethod):
    """
    Verifies that protected paths are enforced by IntentGuard.
    Used for immutability rules like safety.charter_immutable.

    SYNC: Checks filesystem paths and configuration files.
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

        # Check SSOT: Rule declares protected_paths
        protected_paths = rule_data.get("protected_paths", [])
        if not protected_paths:
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' must declare 'protected_paths' for path protection enforcement.",
                    file_path="none",
                )
            )
            return findings

        # Verify expected patterns if specified
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


# ID: code-pattern-enforcement
# ID: 245f2998-1a13-4c14-8e0f-da543417a63d
class CodePatternEnforcement(EnforcementMethod):
    """
    Verifies that code patterns are detected via AST scanning.
    Used for rules like safety.no_dangerous_execution.

    SYNC: Checks AST patterns in source code.
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

        # Check SSOT: Rule declares detection method
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

        # Verify required patterns
        for required in self.required_patterns:
            if required not in patterns:
                findings.append(
                    self._create_finding(
                        f"Rule '{self.rule_id}' missing required pattern: '{required}'",
                        file_path="none",
                    )
                )

        return findings


# ID: single-instance-enforcement
# ID: befdd49a-3cb9-4868-8480-9c7ba03ee61c
class SingleInstanceEnforcement(EnforcementMethod):
    """
    Verifies that exactly one instance of something exists.
    Used for rules like safety.single_active_constitution.

    SYNC: Checks filesystem for file existence and content.
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

        # Verify target file exists
        if not target_path.exists():
            findings.append(
                self._create_finding(
                    f"Rule '{self.rule_id}' requires '{self.target_file}' to exist.",
                    file_path=self.target_file,
                )
            )
            return findings

        # Verify it references exactly one constitution
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


# ============================================================================
# ASYNCHRONOUS ENFORCEMENT METHODS (Database/Network-based)
# ============================================================================


# ID: knowledge-ssot-enforcement
# ID: 1aea6ed5-86e9-4034-9ec9-053738e0c65f
class KnowledgeSSOTEnforcement(AsyncEnforcementMethod):
    """
    Verifies that operational knowledge exists in DB tables (SSOT).
    Checks table existence, row counts, and primary key uniqueness.

    ASYNC: Requires database queries via async session.
    """

    # FIXED (RUF012): Annotated with ClassVar to satisfy strict linting.
    _SSOT_TABLES: ClassVar[list[dict[str, str]]] = [
        {
            "name": "cli_registry",
            "rule_id": "db.cli_registry_in_db",
            "table": "core.cli_commands",
            "primary_key": "name",
        },
        {
            "name": "llm_resources",
            "rule_id": "db.llm_resources_in_db",
            "table": "core.llm_resources",
            "primary_key": "name",
        },
        {
            "name": "cognitive_roles",
            "rule_id": "db.cognitive_roles_in_db",
            "table": "core.cognitive_roles",
            "primary_key": "role",
        },
        {
            "name": "domains",
            "rule_id": "db.domains_in_db",
            "table": "core.domains",
            "primary_key": "key",
        },
    ]

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: bf759401-01f8-41b3-854b-77d20331c002
    async def verify_async(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        """
        Async verification - checks DB tables.
        """

        from shared.infrastructure.database.session_manager import get_session

        findings = []

        try:
            async with get_session() as session:
                for cfg in self._SSOT_TABLES:
                    findings.extend(await self._check_table(session, cfg))
        except Exception as e:
            logger.error("Failed DB audit in KnowledgeSSOTEnforcement: %s", e)
            findings.append(
                self._create_finding(
                    f"DB SSOT audit failed (session or query error): {e}",
                    file_path="DB",
                )
            )

        return findings

    async def _check_table(self, session, cfg: dict) -> list[AuditFinding]:
        """Check a single SSOT table for existence, row count, and PK uniqueness."""
        from sqlalchemy import text

        findings = []
        table = cfg["table"]
        pk = cfg["primary_key"]
        rule_id = cfg["rule_id"]
        name = cfg["name"]

        # 1) Basic table presence + row count
        try:
            count_stmt = text(f"select count(*) as n from {table}")
            result = await session.execute(count_stmt)
            row_count = int(result.scalar_one())
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"DB SSOT table check failed for '{name}' ({table}): {e}",
                    file_path="DB",
                )
            )
            return findings

        if row_count == 0:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"DB SSOT table '{table}' is empty. "
                        "Operational knowledge must exist in DB."
                    ),
                    file_path="DB",
                )
            )
            return findings

        # 2) Primary key uniqueness
        try:
            dup_stmt = text(
                f"""
                SELECT {pk}, COUNT(*) as cnt
                FROM {table}
                GROUP BY {pk}
                HAVING COUNT(*) > 1
                """
            )
            result = await session.execute(dup_stmt)
            duplicates = result.fetchall()

            if duplicates:
                dup_keys = [str(row[0]) for row in duplicates]
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=AuditSeverity.ERROR,
                        message=f"DB SSOT table '{table}' has duplicate primary keys: {', '.join(dup_keys)}",
                        file_path="DB",
                    )
                )
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id=rule_id,
                    severity=AuditSeverity.ERROR,
                    message=f"DB SSOT PK uniqueness check failed for '{name}': {e}",
                    file_path="DB",
                )
            )

        return findings


__all__ = [
    "AsyncEnforcementMethod",
    "CodePatternEnforcement",
    "EnforcementMethod",
    "KnowledgeSSOTEnforcement",
    "PathProtectionEnforcement",
    "RuleEnforcementCheck",
    "SingleInstanceEnforcement",
]
