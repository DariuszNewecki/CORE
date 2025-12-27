# src/mind/logic/engines/ast_gate/checks/logging_checks.py
"""Logging standards checks for constitutional enforcement."""

from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: d294b212-259a-459f-a243-ba0a5b10b307
class LoggingChecks:
    """Logging standards enforcement."""

    @staticmethod
    # ID: 1e3c1afb-e68a-476e-a200-4d186cc3ee52
    def check_no_print_statements(tree: ast.AST) -> list[str]:
        """Enforce logging.single_logging_system: forbid print() calls."""
        findings: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func_name = ASTHelpers.full_attr_name(node.func)
            if func_name == "print":
                findings.append(
                    f"Line {ASTHelpers.lineno(node)}: Replace print() with logger.info() or logger.debug()"
                )

        return findings
