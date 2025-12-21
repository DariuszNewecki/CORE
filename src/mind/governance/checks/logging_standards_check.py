# src/mind/governance/checks/logging_standards_check.py
"""
Constitutional check for logging standards compliance.

Enforces:
- Use of shared.logger.getLogger() for operational logging
- CLI commands separate command output from operational logging
- No f-strings in logger calls (lazy formatting)
- No print(), rich.console, or direct stdout writes except in CLI layer
- No Rich Progress bars - use logger.debug() for progress indication

Implementation:
- AST-based checks for forbidden imports/calls/patterns
- Path-based CLI layer detection for remediation guidance

Note:
- CLI command output MAY go to stdout using approved mechanisms (e.g., typer.echo())
- Operational events MUST use logger.* (never mixed into structured stdout output)

Ref: .intent/charter/standards/logging_standards.json
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: logging-standards-enforcement
# ID: eb17df77-a253-4c9f-bd6a-e652756722dc
class LoggingStandardsEnforcement(EnforcementMethod):
    """
    Context-aware validation of logging standards using AST parsing.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: ea5c0673-3808-4345-b2f0-b2d14ddd3a5e
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """Execute the logging standards check across all Python files."""
        findings = []
        for file_path in context.python_files:
            findings.extend(self._check_file(context, file_path))
        return findings

    def _check_file(
        self, context: AuditorContext, file_path: Path
    ) -> list[AuditFinding]:
        """Check a single file for logging violations using AST analysis."""
        if self._is_exempted(file_path):
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            findings = []
            findings.extend(self._check_forbidden_imports_ast(context, file_path, tree))
            findings.extend(self._check_forbidden_calls_ast(context, file_path, tree))
            findings.extend(self._check_print_calls_ast(context, file_path, tree))
            findings.extend(self._check_stdout_writes_ast(context, file_path, tree))
            findings.extend(
                self._check_fstring_logger_calls_ast(context, file_path, tree)
            )
            return findings

        except SyntaxError as e:
            logger.debug("Syntax error in %s: %s", file_path, e)
            return []
        except Exception as e:
            logger.error("Failed to check file %s: %s", file_path, e)
            return []

    def _is_cli_layer(self, rel_path: Path) -> bool:
        """
        Check if file is part of the CLI layer.

        CLI layer is allowed to use Rich Console for human-readable output, and is
        expected to emit structured command output to stdout via approved mechanisms
        (e.g., typer.echo()).
        """
        path_str = str(rel_path).replace("\\", "/")
        return (
            "body/cli" in path_str
            or "cli_utils.py" in path_str
            or "will/cli_logic" in path_str
        )

    def _check_forbidden_imports_ast(
        self, context: AuditorContext, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for forbidden Rich imports (logging.use_standard_library)."""
        findings = []
        rel_path = file_path.relative_to(context.repo_path)
        is_cli = self._is_cli_layer(rel_path)

        forbidden_checks = [
            (
                "rich.console",
                "Console",
                "logging.single_logging_system: Logic layers must use logger, not Rich Console.",
                not is_cli,
            ),
            (
                "rich.progress",
                "Progress",
                "logging.progress_indication: Replace Rich progress indicators with logger.debug() progress logs.",
                True,
            ),
            (
                "rich",
                "print",
                "logging.single_logging_system: Do not use rich.print; use logger.* for operational logs and approved CLI output mechanisms for command output.",
                True,
            ),
        ]

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    import_name = alias.name
                    for f_mod, f_name, msg, enforce in forbidden_checks:
                        if enforce and module == f_mod and import_name == f_name:
                            findings.append(
                                self._create_finding(
                                    message=msg,
                                    file_path=str(rel_path),
                                    line_number=node.lineno,
                                )
                            )

        return findings

    def _check_forbidden_calls_ast(
        self, context: AuditorContext, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for forbidden calls (logging.use_standard_library/log_progress)."""
        findings = []
        rel_path = file_path.relative_to(context.repo_path)
        is_cli = self._is_cli_layer(rel_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = self._get_call_name(node)

            # Rich Console is allowed in CLI entry points for human output,
            # but forbidden in non-CLI layers.
            if not is_cli and call_name == "console.print":
                findings.append(
                    self._create_finding(
                        message="Replace console.print() with logger.info()/logger.debug() for operational messages.",
                        file_path=str(rel_path),
                        line_number=node.lineno,
                    )
                )

            if not is_cli and call_name == "console.status":
                findings.append(
                    self._create_finding(
                        message="Replace console.status() with logger.info() milestones and logger.debug() progress logs.",
                        file_path=str(rel_path),
                        line_number=node.lineno,
                    )
                )

            if call_name == "Progress":
                findings.append(
                    self._create_finding(
                        message="Replace Progress() with logger.debug() progress logs.",
                        file_path=str(rel_path),
                        line_number=node.lineno,
                    )
                )

        return findings

    def _check_print_calls_ast(
        self, context: AuditorContext, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for print() usage (logging.use_standard_library)."""
        findings = []
        rel_path = file_path.relative_to(context.repo_path)
        is_cli = self._is_cli_layer(rel_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Name) and node.func.id == "print":
                if is_cli:
                    msg = (
                        "Replace print() with approved CLI output mechanisms: "
                        "use typer.echo() for structured --format json|yaml output, "
                        "and console.print() for human-readable CLI output. "
                        "Do NOT emit structured output via logger.*."
                    )
                else:
                    msg = "Replace print() with logger.info() or logger.debug() for operational messages."

                findings.append(
                    self._create_finding(
                        message=msg, file_path=str(rel_path), line_number=node.lineno
                    )
                )

        return findings

    def _check_stdout_writes_ast(
        self, context: AuditorContext, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """
        Check for direct sys.stdout.write / sys.stderr.write usage.

        Standard forbids these as they bypass consistent logging, and in CLI commands
        they are not the approved output mechanism (typer.echo() is).
        """
        findings = []
        rel_path = file_path.relative_to(context.repo_path)
        is_cli = self._is_cli_layer(rel_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = self._get_call_name(node)
            if call_name in ("sys.stdout.write", "sys.stderr.write"):
                if is_cli:
                    msg = (
                        "Replace direct sys.stdout/sys.stderr writes with typer.echo() "
                        "for CLI command output."
                    )
                else:
                    msg = "Replace direct sys.stdout/sys.stderr writes with logger.* for operational output."

                findings.append(
                    self._create_finding(
                        message=msg, file_path=str(rel_path), line_number=node.lineno
                    )
                )

        return findings

    def _check_fstring_logger_calls_ast(
        self, context: AuditorContext, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for f-strings in logger calls (logging.use_lazy_formatting)."""
        findings = []
        rel_path = file_path.relative_to(context.repo_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = self._get_call_name(node)

            if any(
                call_name.endswith(f".{m}")
                for m in [
                    "debug",
                    "info",
                    "warning",
                    "error",
                    "critical",
                    "exception",
                ]
            ):
                if node.args and isinstance(node.args[0], ast.JoinedStr):
                    findings.append(
                        self._create_finding(
                            message="Do not use f-strings in logger calls. Use lazy % formatting.",
                            file_path=str(rel_path),
                            line_number=node.lineno,
                        )
                    )

        return findings

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract full name of function call from AST node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return self._get_attribute_chain(node.func)
        return ""

    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Build attribute chain (e.g. console.print, sys.stdout.write)."""
        parts: list[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
        return ".".join(parts)

    def _is_exempted(self, file_path: Path) -> bool:
        """Check if file is exempted (scripts, tests)."""
        path_str = str(file_path).replace("\\", "/")
        if "tests/" in path_str or "test_" in file_path.name:
            return True
        return False


# ID: 88e5ab7a-5f4d-401d-abf6-280a27e653eb
class LoggingStandardsCheck(RuleEnforcementCheck):
    """
    Context-aware validation of logging standards using AST parsing.

    Ref: .intent/charter/standards/logging_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "logging.single_logging_system",
        "logging.progress_indication",
        "logging.error_logging",
        "logging.log_level_usage",
        "logging.message_format",
        "logging.cli_command_output",
    ]

    policy_file: ClassVar = settings.paths.policy("logging_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        LoggingStandardsEnforcement(rule_id="logging.single_logging_system"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
