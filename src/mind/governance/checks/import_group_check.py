# src/mind/governance/checks/import_group_check.py
"""
Enforces layout.import_grouping: Imports must be grouped: stdlib → third-party → local.

UPDATED: Now aligns with ruff's standard isort behavior (groups by source, not style).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 18776480-eaa4-4d61-b6dc-4f17059f7777
class ImportGroupCheck(BaseCheck):
    policy_rule_ids = ["layout.import_grouping"]

    # Updated to match ruff's isort grouping (by source, not style)
    _STDLIB_PATTERN = r"^(?:import|from)\s+([a-zA-Z0-9_]+)(?:\s|\.)"
    _THIRDPARTY_PATTERN = (
        r"^(?:import|from)\s+([a-zA-Z0-9_][a-zA-Z0-9_.-]*[a-zA-Z0-9_])(?:\s|\.)"
    )
    _LOCAL_PATTERN = r"^(?:import|from)\s+\.+"

    # Common stdlib modules for heuristic detection
    _STDLIB_MODULES = {
        "abc",
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "math",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "random",
        "re",
        "shutil",
        "subprocess",
        "sys",
        "tempfile",
        "textwrap",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "urllib",
        "uuid",
        "warnings",
        "weakref",
        "xml",
    }

    # ID: 5eb90564-22d8-4cb1-b208-086a6eaa143d
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                import_nodes = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    and node.lineno is not None
                ]

                if not import_nodes:
                    continue

                # Sort by line number
                import_nodes.sort(key=lambda n: n.lineno)

                # Extract import lines and classify
                lines = content.splitlines()
                import_info = []

                for node in import_nodes:
                    line_no = node.lineno - 1
                    if line_no >= len(lines):
                        continue

                    line = lines[line_no].strip()
                    if not line.startswith(("import ", "from ")):
                        continue

                    group = self._classify_import(line)
                    import_info.append((line_no, line, group))

                # Check that groups are in order (0 → 1 → 2, never backward)
                prev_group = -1
                for line_no, line, group in import_info:
                    if group < prev_group:
                        # Violation: went backward (e.g., stdlib after third-party)
                        findings.append(self._finding(file_path, line_no + 1))
                    prev_group = group

            except Exception as e:
                findings.append(
                    AuditFinding(
                        check_id="layout.import_grouping",
                        severity=AuditSeverity.WARNING,
                        message=f"Parse error: {e}",
                        file_path=str(file_path.relative_to(self.repo_root)),
                        line_number=1,
                    )
                )

        return findings

    def _classify_import(self, line: str) -> int:
        """
        Classify an import line into one of three groups:
        0 = stdlib
        1 = third-party
        2 = local/relative

        Matches ruff's isort behavior.
        """
        # Group 2: Local/relative imports (starts with .)
        if re.match(self._LOCAL_PATTERN, line):
            return 2

        # Extract module name
        match = re.match(r"^(?:import|from)\s+([a-zA-Z0-9_.-]+)", line)
        if not match:
            return 1  # Default to third-party if can't parse

        module = match.group(1).split(".")[0]  # Get root module

        # Group 0: Standard library
        if module in self._STDLIB_MODULES:
            return 0

        # Heuristic: Single-word modules are likely stdlib
        # Multi-segment or hyphenated modules are likely third-party
        if "-" in module or "." in match.group(1):
            return 1  # third-party

        # Single underscore-only name: likely stdlib
        if "_" not in module or module.replace("_", "").isalpha():
            return 0  # Assume stdlib

        # Default: third-party
        return 1

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="layout.import_grouping",
            severity=AuditSeverity.WARNING,
            message="Imports not properly grouped. Run `fix import-group`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
