# src/mind/governance/checks/runtime_validation_check.py

"""
Constitutional enforcement: agent.execution.require_runtime_validation

Ensures that dangerous code execution includes runtime validation of inputs,
not just parse-time validation.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 5f409021-f114-4db8-92c9-1b2f8372340f
class RuntimeValidationCheck(BaseCheck):
    """
    Enforces agent.execution.require_runtime_validation: Code must validate inputs at runtime.
    """

    policy_rule_ids = ["agent.execution.require_runtime_validation"]

    # Only check in trusted domains (where dangerous functions are allowed)
    CHECKED_DOMAINS = [
        "mind.governance",
        "mind.policies",
        "body.cli.logic",
        "body.cli.commands",
        "core",
    ]

    DANGEROUS_FUNCTIONS = ["eval", "exec", "compile"]

    # ID: 37a6aaf1-d9ca-4b8d-9fdf-fb107a679a21
    def execute(self) -> list[AuditFinding]:
        """Check that dangerous functions have runtime validation."""
        findings = []

        # Query symbols from database (SSOT)
        for symbol_data in self.context.symbols_list:
            # Only check functions
            if symbol_data.get("type") not in ("function", "method"):
                continue

            module = symbol_data.get("module", "")

            # Only check trusted domains (where dangerous functions are allowed)
            if not any(module.startswith(d) for d in self.CHECKED_DOMAINS):
                continue

            symbol_path = symbol_data.get("name", "")
            file_path = symbol_data.get("file_path", "")

            if not file_path:
                continue

            file_path_obj = Path(self.context.repo_path) / file_path
            if not file_path_obj.exists():
                continue

            try:
                content = file_path_obj.read_text(encoding="utf-8")
                tree = ast.parse(content)

                # Find the specific function
                for node in ast.walk(tree):
                    if not isinstance(node, ast.FunctionDef):
                        continue

                    if not symbol_path.endswith(f".{node.name}"):
                        continue

                    # Check if function uses dangerous primitives
                    violations = self._check_runtime_validation(
                        node, content, file_path
                    )
                    findings.extend(violations)

            except Exception:
                continue

        return findings

    def _check_runtime_validation(
        self,
        func_node: ast.FunctionDef,
        file_content: str,
        file_path: str,
    ) -> list[AuditFinding]:
        """Check that dangerous function calls have runtime validation."""
        findings = []

        # Find dangerous function calls
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue

            func_name = None
            if isinstance(node, ast.Name):
                func_name = node.func.id

            if func_name not in self.DANGEROUS_FUNCTIONS:
                continue

            line_num = node.lineno

            # Check for runtime validation markers
            func_source = ast.get_source_segment(file_content, func_node) or ""

            # Look for validation patterns BEFORE the dangerous call
            lines_before_call = func_source.split("\n")[: line_num - func_node.lineno]
            context_before = "\n".join(lines_before_call)

            has_runtime_validation = any(
                [
                    # Explicit runtime validation comment
                    "runtime validation" in context_before.lower(),
                    "runtime check" in context_before.lower(),
                    # Validation loops/checks before the call
                    "for node in ast.walk" in context_before,
                    "if type(node) not in" in context_before,
                    # Input validation before call
                    "if not " in context_before and "raise" in context_before,
                    "assert " in context_before,
                ]
            )

            if not has_runtime_validation:
                findings.append(
                    AuditFinding(
                        check_id=self.policy_rule_ids[0],
                        severity=AuditSeverity.ERROR,
                        message=f"Dangerous function '{func_name}()' missing runtime validation. "
                        f"Add validation checks before execution or 'Runtime validation:' comment.",
                        location=f"{file_path}:{line_num}",
                        context={
                            "function": func_name,
                            "required": "Runtime validation comment or validation code before execution",
                        },
                    )
                )

        return findings
