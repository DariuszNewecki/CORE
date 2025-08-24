# src/system/governance/checks/style_checks.py
"""
Auditor checks for code style and convention compliance, as defined in
.intent/policies/code_style_policy.yaml.
"""
from __future__ import annotations

import ast

from system.governance.models import AuditFinding, AuditSeverity


class StyleChecks:
    """Container for code style and convention constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context
        self.style_policy = self.context.load_config(
            self.context.intent_dir / "policies" / "code_style_policy.yaml"
        )

    # CAPABILITY: audit.check.code_style
    def check_module_conventions(self) -> list[AuditFinding]:
        """Verifies that Python modules adhere to documented style conventions."""
        findings = []
        check_name = "Code Style & Conventions"

        rules = {rule["id"]: rule for rule in self.style_policy.get("rules", [])}
        files_to_check = {
            s["file"]
            for s in self.context.symbols_list
            if s.get("file", "").endswith(".py")
        }

        violations_found = 0
        for file_rel_path in sorted(list(files_to_check)):
            file_abs_path = self.context.repo_root / file_rel_path
            try:
                source_code = file_abs_path.read_text(encoding="utf-8")
                lines = source_code.splitlines()
                tree = ast.parse(source_code)

                # Rule: require_filepath_comment
                if "require_filepath_comment" in rules:
                    if not lines or not lines[0].strip().startswith(
                        f"# {file_rel_path}"
                    ):
                        violations_found += 1
                        findings.append(
                            AuditFinding(
                                AuditSeverity.ERROR,
                                f"Missing or incorrect file path comment on line 1 in '{file_rel_path}'.",
                                check_name,
                            )
                        )

                # Rule: require_module_docstring
                if "require_module_docstring" in rules:
                    has_docstring = (
                        tree.body
                        and isinstance(tree.body[0], ast.Expr)
                        and isinstance(tree.body[0].value, ast.Constant)
                    )
                    if not has_docstring:
                        violations_found += 1
                        findings.append(
                            AuditFinding(
                                AuditSeverity.ERROR,
                                f"Missing required module-level docstring in '{file_rel_path}'.",
                                check_name,
                            )
                        )

                # Rule: require_future_annotations
                if "require_future_annotations" in rules:
                    has_future_import = any(
                        isinstance(node, ast.ImportFrom)
                        and node.module == "__future__"
                        and any(alias.name == "annotations" for alias in node.names)
                        for node in tree.body
                    )
                    if not has_future_import:
                        violations_found += 1
                        findings.append(
                            AuditFinding(
                                AuditSeverity.ERROR,
                                f"Missing 'from __future__ import annotations' in '{file_rel_path}'.",
                                check_name,
                            )
                        )

            except Exception as e:
                violations_found += 1
                findings.append(
                    AuditFinding(
                        AuditSeverity.ERROR,
                        f"Could not parse or check file '{file_rel_path}': {e}",
                        check_name,
                    )
                )

        if violations_found == 0:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    "All modules adhere to style and convention policies.",
                    check_name,
                )
            )

        return findings
