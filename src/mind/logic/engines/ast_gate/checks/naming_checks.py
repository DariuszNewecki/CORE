# src/mind/logic/engines/ast_gate/checks/naming_checks.py
"""Naming and structure checks for constitutional enforcement."""

from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: 5d744901-7a32-420f-9c62-2b7cf4119c6c
class NamingChecks:
    """Naming convention and structural checks."""

    @staticmethod
    # ID: 3143745b-3095-4aa4-a7c9-5c8d9b770a95
    def check_cli_async_helpers_private(tree: ast.AST) -> list[str]:
        """
        Enforce: Async helpers in CLI must be private (start with _).

        ROI: Eliminates 92 violations from CliNamingCheck.
        """
        findings: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue

            if node.name.startswith("_"):
                continue

            if node.name.startswith("__") and node.name.endswith("__"):
                continue

            findings.append(
                f"Line {ASTHelpers.lineno(node)}: Async helper '{node.name}' must be private (start with _)"
            )

        return findings

    @staticmethod
    # ID: 808680cf-71de-4267-bf08-a734239ab10c
    def check_test_file_naming(file_path: str) -> list[str]:
        """
        Enforce: Test files must be prefixed with 'test_'.

        ROI: Eliminates 9 violations from PythonModuleNamingCheck.
        """
        findings: list[str] = []
        filename = file_path.split("/")[-1]

        if "test" in filename.lower():
            if not filename.startswith("test_"):
                if "test_generation" not in file_path:
                    findings.append(
                        f"Test file '{filename}' must be prefixed with 'test_'"
                    )

        return findings

    @staticmethod
    # ID: 1768504f-6c1c-48de-8401-2d99f775627a
    def check_max_file_lines(
        tree: ast.AST, file_path: str, limit: int = 400
    ) -> list[str]:
        """
        Enforce: Files must not exceed line limits.

        ROI: Eliminates 8 violations from CodeConventionsCheck.
        """
        # Count lines in the source
        line_count = 0
        for node in ast.walk(tree):
            if hasattr(node, "lineno"):
                line_count = max(line_count, node.lineno)

        findings: list[str] = []
        if line_count > limit:
            findings.append(f"Module has {line_count} lines, exceeds limit of {limit}")

        return findings

    @staticmethod
    # ID: a9b8c7d6-e5f4-3a2b-1c0d-9e8f7a6b5c4d
    def check_max_function_length(tree: ast.AST, limit: int = 50) -> list[str]:
        """
        Enforce: Functions must not exceed line limits.

        Constitutional Rule: code_standards.max_function_lines
        Default limit: 50 lines per function

        ROI: Replaces LLM gate with deterministic AST check.
        """
        findings: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Skip magic methods and private helpers
            if node.name.startswith("__") and node.name.endswith("__"):
                continue

            # Calculate function length
            if hasattr(node, "end_lineno") and hasattr(node, "lineno"):
                func_length = node.end_lineno - node.lineno + 1

                if func_length > limit:
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: Function '{node.name}' has {func_length} lines, "
                        f"exceeds limit of {limit}"
                    )

        return findings
