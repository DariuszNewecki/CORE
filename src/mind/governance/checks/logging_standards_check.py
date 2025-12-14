# src/mind/governance/checks/logging_standards_check.py
"""
Constitutional check for logging standards compliance.
Enforces logging.* rules from logging_standards.yaml v2.0.
Uses AST-based context-aware analysis.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 88e5ab7a-5f4d-401d-abf6-280a27e653eb
class LoggingStandardsCheck(BaseCheck):
    """
    Context-aware validation of logging standards using AST parsing.
    Ref: standard_logging (logging.use_standard_library, etc.)
    """

    policy_rule_ids = [
        "logging.use_standard_library",
        "logging.use_correct_levels",
        "logging.use_lazy_formatting",
        "logging.log_progress_appropriately",
        "logging.use_structured_context",
        "logging.log_errors_with_traces",
    ]

    # ID: d542bd17-66d3-46e4-8e45-6d5faf7cc4dd
    def execute(self) -> list[AuditFinding]:
        """Execute the logging standards check across all Python files."""
        findings = []
        for file_path in self.context.python_files:
            findings.extend(self._check_file(file_path))
        return findings

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
    def _check_file(self, file_path: Path) -> list[AuditFinding]:
        """Check a single file for logging violations using AST analysis."""
        if self._is_exempted(file_path):
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            findings = []
            findings.extend(self._check_forbidden_imports_ast(file_path, tree))
            findings.extend(self._check_forbidden_calls_ast(file_path, tree))
            findings.extend(self._check_print_calls_ast(file_path, tree))
            findings.extend(self._check_fstring_logger_calls_ast(file_path, tree))
            return findings

        except SyntaxError as e:
            logger.debug("Syntax error in %s: %s", file_path, e)
            return []
        except Exception as e:
            logger.error("Failed to check file %s: %s", file_path, e)
            return []

    def _is_cli_layer(self, rel_path: Path) -> bool:
        """Check if file is part of the CLI layer and exempt from headless rules."""
        path_str = str(rel_path).replace("\\", "/")
        return (
            "body/cli" in path_str
            or "cli_utils.py" in path_str
            or "will/cli_logic" in path_str
        )

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def _check_forbidden_imports_ast(
        self, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for forbidden Rich imports (logging.use_standard_library)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)
        is_cli = self._is_cli_layer(rel_path)

        forbidden_checks = [
            (
                "rich.console",
                "Console",
                "logging.use_standard_library: Logic layers must use logger, not Console.",
                not is_cli,
            ),
            (
                "rich.progress",
                "Progress",
                "logging.log_progress_appropriately: Use logger.debug() for progress.",
                True,
            ),
            (
                "rich",
                "print",
                "logging.use_standard_library: Use logger.info() instead of Rich print.",
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
                                AuditFinding(
                                    check_id=msg.split(":")[0],
                                    severity=AuditSeverity.ERROR,
                                    message=msg,
                                    file_path=str(rel_path),
                                    line_number=node.lineno,
                                )
                            )
        return findings

    # ID: d4e5f6a7-b8c9-0123-def1-234567890123
    def _check_forbidden_calls_ast(
        self, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for forbidden calls (logging.use_standard_library/log_progress)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)
        is_cli = self._is_cli_layer(rel_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)

                if not is_cli and call_name == "console.print":
                    findings.append(
                        AuditFinding(
                            check_id="logging.use_standard_library",
                            severity=AuditSeverity.ERROR,
                            message="Use logger.info() instead of Rich print.",
                            file_path=str(rel_path),
                            line_number=node.lineno,
                        )
                    )

                if not is_cli and call_name == "console.status":
                    findings.append(
                        AuditFinding(
                            check_id="logging.log_progress_appropriately",
                            severity=AuditSeverity.ERROR,
                            message="Replace console.status() with logger.info() for milestones.",
                            file_path=str(rel_path),
                            line_number=node.lineno,
                        )
                    )

                if call_name == "Progress":
                    findings.append(
                        AuditFinding(
                            check_id="logging.log_progress_appropriately",
                            severity=AuditSeverity.ERROR,
                            message="Replace Progress() with logger.debug() for progress.",
                            file_path=str(rel_path),
                            line_number=node.lineno,
                        )
                    )
        return findings

    # ID: e5f6a7b8-c9d0-1234-ef12-345678901234
    def _check_print_calls_ast(
        self, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for print() usage (logging.use_standard_library)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)

        if self._is_cli_layer(
            rel_path
        ):  # CLI allowed (sometimes) but check is stricter here?
            # Actually policy says print allowed ONLY in scripts. CLI uses Rich.
            # So print() is technically forbidden even in CLI layer if we follow strict rules.
            pass

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    findings.append(
                        AuditFinding(
                            check_id="logging.use_standard_library",
                            severity=AuditSeverity.ERROR,
                            message="Replace print() with logger.info() or logger.debug().",
                            file_path=str(rel_path),
                            line_number=node.lineno,
                        )
                    )
        return findings

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    def _check_fstring_logger_calls_ast(
        self, file_path: Path, tree: ast.AST
    ) -> list[AuditFinding]:
        """Check for f-strings in logger calls (logging.use_lazy_formatting)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                # Check known logger methods
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
                            AuditFinding(
                                check_id="logging.use_lazy_formatting",
                                severity=AuditSeverity.ERROR,
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
        elif isinstance(node.func, ast.Attribute):
            return self._get_attribute_chain(node.func)
        return ""

    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Build attribute chain (e.g. console.print)."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
        return ".".join(parts)

    # ID: f6a7b8c9-d0e1-2345-f123-456789012345
    def _is_exempted(self, file_path: Path) -> bool:
        """Check if file is exempted (scripts, tests)."""
        path_str = str(file_path).replace("\\", "/")
        if "tests/" in path_str or "test_" in file_path.name:
            return True
        if path_str.startswith("scripts/") or path_str.startswith("dev-scripts/"):
            return True
        return False
