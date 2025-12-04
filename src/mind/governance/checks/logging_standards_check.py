# src/mind/governance/checks/logging_standards_check.py
"""
Constitutional check for logging standards compliance.
Enforces LOG-001 through LOG-006 from logging_standards.yaml policy.
"""

from __future__ import annotations

import re
from pathlib import Path

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: f8e7d6c5-b4a3-9281-c0d1-e2f3g4h5i6j7
class LoggingStandardsCheck(BaseCheck):
    """Validates that code follows constitutional logging standards."""

    policy_rule_ids = ["LOG-001", "LOG-002", "LOG-003", "LOG-004", "LOG-005", "LOG-006"]

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
    def execute(self) -> list[AuditFinding]:
        """Execute the logging standards check across all Python files."""
        findings = []

        for file_path in self.context.python_files:
            findings.extend(self._check_file(file_path))

        return findings

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
    def _check_file(self, file_path: Path) -> list[AuditFinding]:
        """Check a single file for logging violations."""
        # Skip exempted paths
        if self._is_exempted(file_path):
            return []

        findings = []

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Check for forbidden imports (LOG-001)
            findings.extend(self._check_forbidden_imports(file_path, lines))

            # Check for forbidden patterns (LOG-001, LOG-004)
            findings.extend(self._check_forbidden_patterns(file_path, lines))

            # Check for print() usage (LOG-001)
            findings.extend(self._check_print_usage(file_path, lines))

            # Check for lazy formatting violations (LOG-003)
            findings.extend(self._check_lazy_formatting(file_path, lines))

        except Exception as e:
            logger.error("Failed to check file %s: %s", file_path, e)

        return findings

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def _check_forbidden_imports(
        self, file_path: Path, lines: list[str]
    ) -> list[AuditFinding]:
        """Check for forbidden Rich imports (LOG-001)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)

        # ALLOW Rich Console in CLI commands and interactive logic
        # Paths starting with src/body/cli
        is_cli_layer = "body/cli" in str(rel_path)

        forbidden = [
            # (Pattern, Message, Enforcement_Condition)
            (
                r"from rich\.console import Console",
                "LOG-001: Logic layers must use logger, not Console.",
                not is_cli_layer,
            ),  # Only enforce if NOT in CLI layer
            (
                r"from rich\.progress import.*Progress",
                "LOG-004: Use logger.debug() for progress, not Rich Progress",
                True,
            ),  # Use logger.debug for progress everywhere to avoid screen clutter
            (
                r"from rich import print",
                "LOG-001: Use logger.info() instead of Rich print",
                True,
            ),  # Always forbid top-level print
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, message, should_enforce in forbidden:
                if should_enforce and re.search(pattern, line):
                    findings.append(
                        AuditFinding(
                            check_id="LOG-001",
                            severity=AuditSeverity.ERROR,
                            message=message,
                            file_path=str(rel_path),
                            line_number=line_num,
                        )
                    )

        return findings

    # ID: d4e5f6a7-b8c9-0123-def1-234567890123
    def _check_forbidden_patterns(
        self, file_path: Path, lines: list[str]
    ) -> list[AuditFinding]:
        """Check for forbidden usage patterns (LOG-001, LOG-004)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)
        is_cli_layer = "body/cli" in str(rel_path)

        # Forbidden patterns
        patterns = [
            (
                r"console\.print\(",
                "LOG-001: Replace console.print() with logger.info()",
                not is_cli_layer,
            ),
            (
                r"console\.status\(",
                "LOG-004: Replace console.status() with logger.info() for milestones",
                not is_cli_layer,
            ),
            (
                r"Progress\(",
                "LOG-004: Replace Progress() with logger.debug() for progress",
                True,
            ),  # Progress bars forbidden in logic to ensure clean logs
        ]

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            for pattern, message, should_enforce in patterns:
                if should_enforce and re.search(pattern, line):
                    findings.append(
                        AuditFinding(
                            check_id=(
                                "LOG-004"
                                if "status" in message or "Progress" in message
                                else "LOG-001"
                            ),
                            severity=AuditSeverity.ERROR,
                            message=message,
                            file_path=str(rel_path),
                            line_number=line_num,
                        )
                    )

        return findings

    # ID: e5f6a7b8-c9d0-1234-ef12-345678901234
    def _check_print_usage(
        self, file_path: Path, lines: list[str]
    ) -> list[AuditFinding]:
        """Check for print() usage outside of scripts (LOG-001)."""
        findings = []
        rel_path = file_path.relative_to(self.repo_root)

        for line_num, line in enumerate(lines, 1):
            # Skip comments and docstrings
            stripped = line.strip()
            if (
                stripped.startswith("#")
                or stripped.startswith('"""')
                or stripped.startswith("'''")
            ):
                continue

            # Check for print( usage
            if re.search(r"\bprint\s*\(", line):
                findings.append(
                    AuditFinding(
                        check_id="LOG-001",
                        severity=AuditSeverity.ERROR,
                        message="LOG-001: Replace print() with logger.info() or logger.debug()",
                        file_path=str(rel_path),
                        line_number=line_num,
                    )
                )

        return findings

    def _check_lazy_formatting(
        self, file_path: Path, lines: list[str]
    ) -> list[AuditFinding]:
        """
        Enforce LOG-003: No f-strings in logger calls.
        Pattern: logger.info(f"...") or logger.debug(f"...")
        """
        findings = []
        rel_path = file_path.relative_to(self.repo_root)

        # Regex to find logger calls using f-strings
        # Matches: logger.info(f" or logger.error(f'
        fstring_pattern = (
            r'logger\.(debug|info|warning|error|critical|exception)\(\s*f[\'"]'
        )

        for line_num, line in enumerate(lines, 1):
            if re.search(fstring_pattern, line):
                findings.append(
                    AuditFinding(
                        check_id="LOG-003",
                        severity=AuditSeverity.ERROR,
                        message="LOG-003 Violation: Do not use f-strings in logger calls. Use lazy % formatting.",
                        file_path=str(rel_path),
                        line_number=line_num,
                        context={"line": line.strip()},
                    )
                )
        return findings

    # ID: f6a7b8c9-d0e1-2345-f123-456789012345
    def _is_exempted(self, file_path: Path) -> bool:
        """Check if this file is exempted from logging standards."""
        path_parts = file_path.parts

        # Test files
        if "test" in path_parts or "tests" in path_parts:
            return True

        # Scripts
        if len(path_parts) > 0 and path_parts[0] in ("scripts", "dev-scripts"):
            return True

        # CLI interactive files get exemption for user prompts
        if "interactive" in file_path.name:
            return True

        return False
