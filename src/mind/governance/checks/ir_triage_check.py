# src/mind/governance/checks/ir_triage_check.py
"""
Enforces ir.triage_required: All incidents must have severity and owner assigned.
"""

from __future__ import annotations

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 6a1ab18f-4330-4e4a-8358-33c2ebe29fd0
class IRTriageCheck(BaseCheck):
    """
    Verifies that every incident recorded in the triage log has been
    properly triaged with an assigned Owner and Severity.
    Ref: standard_operations_general (ir.triage_required)
    """

    policy_rule_ids = ["ir.triage_required"]

    # ID: b2d64ca1-4def-496c-b11d-28a58a7a1280
    def execute(self) -> list[AuditFinding]:
        findings = []

        # 1. Locate Log (SSOT)
        log_path = self.context.mind_path / "ir/triage_log.yaml"

        if not log_path.exists():
            # Missing file handles structural compliance elsewhere,
            # but if it's missing, we technically can't be untriaged.
            # We'll return empty here and let FileChecks handle the missing file.
            return []

        # 2. Parse Content
        try:
            content = yaml.safe_load(log_path.read_text(encoding="utf-8")) or {}
            entries = content.get("entries", [])
        except Exception as e:
            logger.error("Failed to parse triage log: %s", e)
            return []  # IRCheck handles syntax errors

        # 3. Validate Triage Metadata
        for i, entry in enumerate(entries):
            entry_id = entry.get("id", f"entry_{i}")

            # Check 1: Severity
            severity = entry.get("severity")
            if not severity or severity not in ["low", "medium", "high", "critical"]:
                findings.append(
                    AuditFinding(
                        check_id="ir.triage_required",
                        severity=AuditSeverity.ERROR,
                        message=f"Incident '{entry_id}' is missing a valid severity.",
                        file_path=str(log_path.relative_to(self.repo_root)),
                        context={"entry": entry_id, "missing": "severity"},
                    )
                )

            # Check 2: Owner
            owner = entry.get("owner")
            if not owner or owner == "TBD":
                findings.append(
                    AuditFinding(
                        check_id="ir.triage_required",
                        severity=AuditSeverity.ERROR,
                        message=f"Incident '{entry_id}' is untriaged (missing owner).",
                        file_path=str(log_path.relative_to(self.repo_root)),
                        context={"entry": entry_id, "missing": "owner"},
                    )
                )

        return findings
