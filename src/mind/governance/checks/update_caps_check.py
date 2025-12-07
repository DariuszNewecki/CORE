# src/mind/governance/checks/update_caps_check.py
"""
Enforces refactor.update_capabilities: All capability modules must define CAPABILITY_ID.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 624c92aa-575c-406f-ac4b-58f5d87558f1
class UpdateCapsCheck(BaseCheck):
    policy_rule_ids = ["refactor.update_capabilities"]

    # ID: 0bd7eb0c-9d01-4181-a211-3428459fc50a
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        caps_dir = Path("src/capabilities")

        if not caps_dir.exists():
            return findings  # No capabilities → no violation

        for cap_file in caps_dir.glob("*.py"):
            if cap_file.name.startswith("_"):
                continue  # Skip __init__.py, etc.

            try:
                content = cap_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(cap_file))

                has_cap_id = False
                for node in ast.walk(tree):
                    # Look for CAPABILITY_ID = "..."
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "CAPABILITY_ID"
                            ):
                                has_cap_id = True
                                break
                        if has_cap_id:
                            break

                if not has_cap_id:
                    findings.append(self._finding(cap_file, 1))

            except Exception as e:
                # Don't crash audit on parse error
                findings.append(
                    AuditFinding(
                        check_id="refactor.update_capabilities",
                        severity=AuditSeverity.WARNING,
                        message=f"Failed to parse {cap_file}: {e}",
                        file_path=str(cap_file.relative_to(self.repo_root)),
                        line_number=1,
                    )
                )

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="refactor.update_capabilities",
            severity=AuditSeverity.WARNING,
            message="Capability module missing CAPABILITY_ID. Run `fix update-caps`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
