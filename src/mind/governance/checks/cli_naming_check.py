# src/mind/governance/checks/cli_naming_check.py
"""
Enforces symbols.cli_async_helpers_private: Async CLI helpers must be private.
"""

from __future__ import annotations

import ast

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: 58eda072-18cf-4fc5-ac41-8a122d62a434
class CliNamingCheck(BaseCheck):
    """
    Scans CLI logic modules to ensure async helper functions are private (start with '_').
    """

    policy_rule_ids = ["symbols.cli_async_helpers_private"]

    # ID: 0a6fd53b-fbc4-4147-a847-e03e5c71ca8f
    def execute(self) -> list[AuditFinding]:
        findings = []
        cli_logic_dir = self.repo_root / "src/body/cli/logic"

        if not cli_logic_dir.exists():
            return findings

        # Scan all python files in cli/logic
        for file_path in cli_logic_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.AsyncFunctionDef):
                        # Check if public (no leading underscore)
                        if not node.name.startswith("_"):
                            findings.append(
                                AuditFinding(
                                    check_id="symbols.cli_async_helpers_private",
                                    severity=AuditSeverity.ERROR,
                                    message=(
                                        f"Public async function '{node.name}' found in CLI logic. "
                                        "Async CLI helpers must be private (prefix with '_')."
                                    ),
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=node.lineno,
                                )
                            )
            except Exception:
                pass

        return findings
