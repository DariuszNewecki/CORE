# src/mind/governance/checks/capability_owner_check.py

"""Provides functionality for the capability_owner_check module."""

from __future__ import annotations

import re

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: 3adcb244-bd0a-45a8-98a7-6bf58f1fda42
class CapabilityOwnerCheck(BaseCheck):
    policy_rule_ids = ["caps.owner_required"]

    # ID: 40d50b0f-01cd-43d7-a41a-baf24f153852
    def execute(self) -> list[AuditFinding]:
        findings = []
        pattern = re.compile(r"# ID: [a-f0-9-]{36}")
        owner_pattern = re.compile(r"# owner:")

        for file_path in self.context.python_files:
            try:
                lines = file_path.read_text().splitlines()
                for i, line in enumerate(lines, 1):
                    if pattern.search(line) and not owner_pattern.search(
                        "\n".join(lines[i - 5 : i + 5])
                    ):
                        findings.append(
                            AuditFinding(
                                check_id="caps.owner_required",
                                severity=AuditSeverity.ERROR,
                                message="Capability ID found without '# owner:' tag in vicinity.",
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=i,
                            )
                        )
            except Exception:
                pass
        return findings
