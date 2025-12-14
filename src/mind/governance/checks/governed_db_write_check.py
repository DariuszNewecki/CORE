# src/mind/governance/checks/governed_db_write_check.py
"""
Enforces db.write_via_governed_cli and Repository Pattern.
Direct DB writes (session.add/commit) are restricted to the Repository/Infrastructure layers.
"""

from __future__ import annotations

import ast

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Valid locations for raw DB writes (Architecture Standard)
ALLOWED_WRITE_SCOPES = [
    "src/services/repositories",
    "src/shared/infrastructure/database",
    # Migrations are special infrastructure
    "src/shared/infrastructure/migrations",
]


# ID: dca11664-1e80-4fc9-84e0-41e169f5a6ae
class GovernedDbWriteCheck(BaseCheck):
    """
    Enforces that direct database mutations via SQLAlchemy session objects
    only occur within designated Repository or Infrastructure layers.
    Upper layers must use these services, not write directly.
    """

    policy_rule_ids = ["db.write_via_governed_cli"]

    # ID: 4d237ba8-c2ad-432f-ba7e-6c7e3df7a29e
    def execute(self) -> list[AuditFinding]:
        findings = []

        for file_path in self.context.python_files:
            # 1. Scope Check: Is this file allowed to write to DB?
            is_allowed = False
            rel_path = str(file_path.relative_to(self.repo_root)).replace("\\", "/")

            for scope in ALLOWED_WRITE_SCOPES:
                if rel_path.startswith(scope):
                    is_allowed = True
                    break

            if is_allowed:
                continue

            # 2. AST Scan for Forbidden Writes
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    # Heuristic: Detect session.add(), session.commit(), etc.
                    # We look for method calls on an object named 'session' or attributes ending in 'session'
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
                                    AuditFinding(
                                        check_id="db.write_via_governed_cli",
                                        severity=AuditSeverity.ERROR,
                                        message=(
                                            f"Direct DB write ('{method_name}') detected outside Repository layer. "
                                            "Use a Service or Repository."
                                        ),
                                        file_path=rel_path,
                                        line_number=node.lineno,
                                        context={
                                            "layer": "application",
                                            "allowed_layers": ALLOWED_WRITE_SCOPES,
                                        },
                                    )
                                )
            except Exception as e:
                logger.debug("Failed to analyze %s: %s", file_path, e)

        return findings
