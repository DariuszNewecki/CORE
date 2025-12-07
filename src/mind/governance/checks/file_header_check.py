# src/mind/governance/checks/file_header_check.py
"""
Enforces the constitutional file header requirement:
Every src/*.py file must start with '# src/path/to/file.py'
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: a0e5a8b7-2068-4e02-bfd6-58cfa11a6631
class FileHeaderCheck(BaseCheck):
    """
    Ensures every Python module under 'src/' has the correct file path header.
    """

    policy_rule_ids = ["layout.src_module_header"]

    # ID: c50adce3-22e6-409f-bcfd-0ee31fcc0478
    def execute(self) -> list[AuditFinding]:
        findings = []
        for file_path in self.context.python_files:
            if not str(file_path).startswith("src/"):
                continue
            rel_path = file_path.relative_to(self.repo_root)
            expected_header = f"# {rel_path}"

            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                first_line = next((line for line in lines if line.strip()), None)
                if first_line != expected_header:
                    findings.append(
                        AuditFinding(
                            check_id="layout.src_module_header",
                            severity=AuditSeverity.ERROR,
                            message=f"Expected header: '{expected_header}'",
                            file_path=str(rel_path),
                            line_number=1,
                        )
                    )
            except Exception as e:
                findings.append(
                    AuditFinding(
                        check_id="layout.src_module_header",
                        severity=AuditSeverity.ERROR,
                        message=f"Failed to read: {e}",
                        file_path=str(rel_path),
                    )
                )
        return findings
