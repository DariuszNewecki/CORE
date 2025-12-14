# src/mind/governance/checks/capability_owner_check.py
"""
Enforces Purity: Ensures no legacy '# owner:' tags remain in source code.
Ownership MUST be defined in the Database (SSOT), not in files.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 3adcb244-bd0a-45a8-98a7-6bf58f1fda42
class CapabilityOwnerCheck(BaseCheck):
    """
    Scans for legacy '# owner:' tags and flags them as Constitutional Violations.
    References: standard_code_purity (Forbidden Pollution)
    """

    policy_rule_ids = ["caps.owner_required", "no_descriptive_pollution"]

    # ID: 40d50b0f-01cd-43d7-a41a-baf24f153852
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # Scan all python files in src
        for file_path in self.src_dir.rglob("*.py"):
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines, 1):
                    if line.strip().startswith("# owner:"):
                        findings.append(
                            AuditFinding(
                                check_id="no_descriptive_pollution",
                                severity=AuditSeverity.ERROR,
                                message=(
                                    "Forbidden Pollution: '# owner:' tag found. "
                                    "Ownership must be managed via the Database/Manifest, "
                                    "not source comments."
                                ),
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=i,
                            )
                        )
            except Exception:
                # If file can't be read, other checks will catch it
                continue

        return findings
