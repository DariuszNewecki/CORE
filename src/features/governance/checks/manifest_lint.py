# src/features/governance/checks/manifest_lint.py
"""
Audits capability manifests for quality issues like placeholder text.
"""

from __future__ import annotations

from typing import List

from shared.models import AuditFinding, AuditSeverity

from features.governance.checks.base_check import BaseCheck


# ID: 3de1c035-00f6-4de2-b778-2b7baaf4594b
class ManifestLintCheck(BaseCheck):
    """Checks for placeholder text in capability manifests."""

    def __init__(self, context):
        super().__init__(context)
        self.linter_policy = self.context.policies.get("capability_linter_policy", {})

    # ID: 6831b833-92a9-4f37-adc9-c3eb7dd3b3d7
    def execute(self) -> List[AuditFinding]:
        """Finds capabilities with placeholder descriptions."""
        findings = []
        rule = next(
            (
                r
                for r in self.linter_policy.get("rules", [])
                if r.get("id") == "caps.no_placeholder_text"
            ),
            None,
        )
        if not rule:
            return []

        for symbol in self.context.symbols_list:
            description = symbol.get("intent", "") or ""
            if any(
                f.lower() in description.lower() for f in ["TBD", "N/A", "Auto-added"]
            ):
                findings.append(
                    AuditFinding(
                        check_id="manifest.lint.placeholder",
                        severity=AuditSeverity.WARNING,
                        message=f"Capability '{symbol.get('key')}' has a placeholder description: '{description}'",
                        file_path=symbol.get("file"),
                        line_number=symbol.get("line_number"),
                    )
                )
        return findings
