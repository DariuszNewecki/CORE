# src/features/governance/checks/style_checks.py
"""
Auditor checks for code style and convention compliance, as defined in
.intent/charter/policies/code_style_policy.yaml.
"""

from __future__ import annotations

import ast

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: fd4ffac0-217f-4b9c-9a70-3a0106779421
class StyleChecks(BaseCheck):
    """Container for code style and convention constitutional checks."""

    def __init__(self, context):
        super().__init__(context)
        self.style_policy = self.context.policies.get("code_style_policy", {})

    # ID: 017a0a53-b5c2-4c50-adf9-5c407fa6eb55
    def execute(self) -> list[AuditFinding]:
        """Verifies that Python modules adhere to documented style conventions."""
        findings = []
        rules = {rule.get("id"): rule for rule in self.style_policy.get("rules", [])}
        files_to_check = {
            s["file_path"]
            for s in self.context.symbols_list
            if s.get("file_path", "").endswith(".py")
        }
        for file_rel_path in sorted(list(files_to_check)):
            file_abs_path = self.repo_root / file_rel_path
            try:
                source_code = file_abs_path.read_text(encoding="utf-8")
                tree = ast.parse(source_code)
                if "style.docstrings_public_apis" in rules:
                    has_docstring = (
                        tree.body
                        and isinstance(tree.body[0], ast.Expr)
                        and isinstance(tree.body[0].value, ast.Constant)
                    )
                    if not has_docstring:
                        findings.append(
                            AuditFinding(
                                check_id="code.style.missing-module-docstring",
                                severity=AuditSeverity.WARNING,
                                message="Missing required module-level docstring.",
                                file_path=file_rel_path,
                            )
                        )
            except Exception as e:
                findings.append(
                    AuditFinding(
                        check_id="code.parser.error",
                        severity=AuditSeverity.ERROR,
                        message=f"Could not parse file: {e}",
                        file_path=file_rel_path,
                    )
                )
        return findings
