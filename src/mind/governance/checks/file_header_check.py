# src/mind/governance/checks/file_header_check.py
"""
Enforces the constitutional file header requirement.
Ref: standard_code_general (layout.src_module_header)
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: a0e5a8b7-2068-4e02-bfd6-58cfa11a6631
class FileHeaderCheck(BaseCheck):
    """
    Ensures every Python module under 'src/' starts with the canonical file path comment.
    Format: # src/path/to/file.py
    """

    policy_rule_ids = ["layout.src_module_header"]

    # ID: c50adce3-22e6-409f-bcfd-0ee31fcc0478
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Iterate all Python files tracked by the context
        for file_path in self.context.python_files:
            try:
                # 1. Normalize Path
                rel_path = file_path.relative_to(self.repo_root)
                posix_path = rel_path.as_posix()  # Force forward slashes (Unix style)

                # 2. Check Scope (src/ only)
                if not posix_path.startswith("src/"):
                    continue

                # 3. Define Expectation
                expected_header = f"# {posix_path}"

                # 4. Verify Content
                lines = file_path.read_text(encoding="utf-8").splitlines()

                # Get first non-empty line to ignore leading whitespace
                first_line = next((line for line in lines if line.strip()), None)

                if first_line != expected_header:
                    findings.append(
                        AuditFinding(
                            check_id="layout.src_module_header",
                            severity=AuditSeverity.ERROR,
                            message=f"Invalid file header. Expected: '{expected_header}'",
                            file_path=posix_path,
                            line_number=1,
                            context={
                                "expected": expected_header,
                                "actual": first_line or "<empty file>",
                                "fix_command": "core-admin fix headers",
                            },
                        )
                    )

            except ValueError:
                # File not relative to repo root (shouldn't happen in standard execution)
                continue
            except Exception as e:
                # Don't crash the audit on single file read errors
                findings.append(
                    AuditFinding(
                        check_id="layout.src_module_header",
                        severity=AuditSeverity.ERROR,
                        message=f"Unable to read file header: {e}",
                        file_path=str(file_path),
                    )
                )

        return findings
