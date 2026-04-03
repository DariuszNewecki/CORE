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
        - logger.*(markup_string) — passing strings with actual Rich markup tags into logger calls

        Rationale: logger calls with Rich objects or markup indicate the logger is being
        used as a rendering surface. Rich objects should go to console.print(); operational
        facts should go to the logger as plain strings.

        NOTE: Plain-text labels like [DRY RUN], [%s], [ERROR] are NOT Rich markup and
        must not trigger this check. Only actual Rich style tags (e.g. [bold], [red],
        [cyan], [/bold]) are violations.

        NOTE: Variable name hinting (e.g. 'table_name') is intentionally excluded —
        it produces too many false positives. Only direct passing of known Rich types
        (Table, Panel, Console, etc.) by their class name is flagged.
        """
        findings: list[str] = []

        # Rich presentation types that must not be passed to logger.
        # Only exact name matches are flagged — no heuristic name guessing.
        _RICH_PRESENTATION_TYPES = {
            "Table",
            "Panel",
            "Console",
            "Columns",
            "Tree",
            "Group",
        }

        # Known Rich style and color names used in markup tags.
        # Only these constitute actual Rich markup — not arbitrary [LABEL] patterns.
        _RICH_STYLES = {
            "bold",
            "dim",
            "italic",
            "underline",
            "strike",
            "reverse",
            "red",
            "green",
            "yellow",
            "blue",
            "magenta",
            "cyan",
            "white",
            "bright_red",
            "bright_green",
            "bright_yellow",
            "bright_blue",
            "bright_magenta",
            "bright_cyan",
            "bright_white",
            "black",
            "bold red",
            "bold green",
            "bold yellow",
            "bold cyan",
            "bold magenta",
            "bold blue",
            "bold white",
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
                if isinstance(arg, ast.Name) and arg.id in _RICH_PRESENTATION_TYPES:
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: logger used as renderer — "
                        f"pass Rich '{arg.id}' to console.print(), not logger."
                    )

                # Pattern 2: logger.info("[bold]text[/bold]") — actual Rich markup in string.
                # Only fires on known Rich style tags or closing tags ([/...]).
                # Does NOT fire on plain-text labels like [DRY RUN], [%s], [ERROR].
                elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    val = arg.value
                    has_closing_tag = "[/" in val
                    has_style_tag = any(f"[{s}]" in val for s in _RICH_STYLES)
                    if has_closing_tag or has_style_tag:
                        findings.append(
                            f"Line {ASTHelpers.lineno(node)}: logger used as renderer — "
                            f"Rich markup detected in log string; use plain text for logger."
                        )

        return findings
