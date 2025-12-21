# src/mind/governance/checks/governed_db_write_check.py
"""
Enforces db.write_via_governed_cli and Repository Pattern.
Direct DB writes (session.add/commit) are restricted to paths defined in policy.

CONSTITUTIONAL: Reads allowed paths from .intent/ instead of hardcoding.

Ref: .intent/charter/standards/data/governance.json
"""

from __future__ import annotations

import ast
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

GOVERNANCE_POLICY = Path(".intent/charter/standards/data/governance.json")


# ID: governed-db-write-enforcement
# ID: a51ecc21-ec92-408c-94ea-b77d93f091f3
class GovernedDbWriteEnforcement(EnforcementMethod):
    """
    Enforces that direct database mutations via SQLAlchemy session objects
    only occur within paths designated by the constitution.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 567928c6-9709-4bb3-a6cc-4a02df7899e7
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Load allowed paths from rule_data (constitutional source of truth)
        allowed_write_paths = rule_data.get("allowed_write_paths", [])

        if not allowed_write_paths:
            logger.warning(
                "No allowed_write_paths found in rule db.write_via_governed_cli. "
                "All DB writes will be flagged!"
            )

        for file_path in context.python_files:
            # 1. Scope Check: Is this file in an allowed path?
            rel_path = str(file_path.relative_to(context.repo_path)).replace("\\", "/")

            if self._is_path_allowed(rel_path, allowed_write_paths):
                continue

            # 2. AST Scan for Forbidden Writes
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    # Detect session.add(), session.commit(), etc.
                    if isinstance(node.func, ast.Attribute):
                        method_name = node.func.attr

                        if method_name in (
                            "add",
                            "add_all",
                            "delete",
                            "merge",
                            "commit",
                            "flush",
                        ):
                            # Check if the object is likely a session
                            is_session_call = False

                            # Case A: self.session.commit()
                            if (
                                isinstance(node.func.value, ast.Attribute)
                                and node.func.value.attr == "session"
                            ):
                                is_session_call = True
                            # Case B: session.commit() (local var)
                            elif (
                                isinstance(node.func.value, ast.Name)
                                and "session" in node.func.value.id
                            ):
                                is_session_call = True

                            if is_session_call:
                                findings.append(
                                    self._create_finding(
                                        message=(
                                            f"Direct DB write ('{method_name}') detected outside allowed paths. "
                                            "Use Repository layer or move to allowed infrastructure path."
                                        ),
                                        file_path=rel_path,
                                        line_number=node.lineno,
                                    )
                                )

            except SyntaxError:
                # Skip files with syntax errors (they'll be caught by other checks)
                continue
            except Exception as e:
                logger.debug("Error scanning %s: %s", rel_path, e)
                continue

        return findings

    def _is_path_allowed(self, file_path_str: str, allowed_paths: list[str]) -> bool:
        """
        Check if file path matches any allowed pattern.
        Uses glob-style patterns (e.g., "src/shared/infrastructure/**")
        """
        for pattern in allowed_paths:
            if fnmatch(file_path_str, pattern):
                return True
        return False


# ID: 4d237ba8-c2ad-432f-ba7e-6c7e3df7a29e
class GovernedDbWriteCheck(RuleEnforcementCheck):
    """
    Enforces that direct database mutations via SQLAlchemy session objects
    only occur within paths designated by the constitution.

    CONSTITUTIONAL PRINCIPLE: Policy defines allowed paths, not code.

    Ref: .intent/charter/standards/data/governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["db.write_via_governed_cli"]

    policy_file: ClassVar[Path] = GOVERNANCE_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        GovernedDbWriteEnforcement(rule_id="db.write_via_governed_cli"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
