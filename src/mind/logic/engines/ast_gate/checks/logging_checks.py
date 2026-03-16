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

    @staticmethod
    # ID: c8b7a6d5-e4f3-4a2b-9c1d-0e8f7a6b5c4d
    def check_logger_not_presentation(tree: ast.AST) -> list[str]:
        """
        Enforces architecture.channels.logger_not_presentation:
        the CORE logger MUST NOT be used as a presentation renderer.

        Detects:
        - logger.*(rich_object) — passing Rich Table/Panel/Console objects into logger calls
        - logger.*(markup_string) — passing strings with Rich markup tags into logger calls

        Rationale: logger calls with Rich objects or markup indicate the logger is being
        used as a rendering surface. Rich objects should go to console.print(); operational
        facts should go to the logger as plain strings.
        """
        findings: list[str] = []

        # Rich presentation types that must not be passed to logger
        rich_presentation_types = {
            "Table",
            "Panel",
            "Console",
            "Columns",
            "Tree",
            "Group",
        }

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func_name = ASTHelpers.full_attr_name(node.func)

            # Only inspect logger.* calls
            if not (func_name and func_name.startswith("logger.")):
                continue

            for arg in node.args:
                # Pattern 1: logger.info(table) — bare Name that is a known Rich type
                if isinstance(arg, ast.Name) and arg.id in rich_presentation_types:
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: logger used as renderer — "
                        f"pass Rich '{arg.id}' to console.print(), not logger."
                    )

                # Pattern 2: logger.info(rich_obj) — variable with a suggestive name
                elif isinstance(arg, ast.Name) and any(
                    hint in arg.id.lower()
                    for hint in ("table", "panel", "markup", "renderable")
                ):
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: logger used as renderer — "
                        f"'{arg.id}' appears to be a presentation object; use console.print()."
                    )

                # Pattern 3: logger.info("[bold]text[/bold]") — Rich markup in string literal
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    val = arg.value
                    if "[/" in val or (val.startswith("[") and "]" in val):
                        findings.append(
                            f"Line {ASTHelpers.lineno(node)}: logger used as renderer — "
                            f"Rich markup detected in log string; use plain text for logger."
                        )

        return findings
