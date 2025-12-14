# src/mind/governance/checks/ir_check.py
"""
Enforces Incident Response (IR) documentation standards.
Validates .intent/mind/ir/triage_log.yaml against 'operations.yaml' rules.
"""

from __future__ import annotations

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 25dc2724-9d94-4ba5-a1cd-c7d93a910d41
class IRCheck(BaseCheck):
    """
     audits the Incident Response log for completeness.
    - ir.timeline: Required for ALL incidents.
    - ir.comms: Required for High/Critical incidents.
    - ir.postmortem: Required for High/Critical incidents.
    """

    policy_rule_ids = ["ir.comms", "ir.postmortem", "ir.timeline", "ir.triage_required"]

    # ID: a0569012-da63-4912-9a1b-ba1c4e9afd4e
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # 1. Locate the IR Log (SSOT)
        # Ref: .intent/mind/ir/triage_log.yaml
        log_path = self.context.mind_path / "ir/triage_log.yaml"

        if not log_path.exists():
            # If the file is missing entirely, that's a structural issue,
            # but we assume "no file" = "no incidents" for now, unless
            # project_manifest requires it.
            # We'll create a finding if the directory is missing.
            if not log_path.parent.exists():
                findings.append(
                    AuditFinding(
                        check_id="ir.triage_required",
                        severity=AuditSeverity.WARNING,
                        message="Incident Response directory (.intent/mind/ir) is missing.",
                        file_path=".intent/mind/ir",
                    )
                )
            return findings

        # 2. Parse YAML
        try:
            data = yaml.safe_load(log_path.read_text(encoding="utf-8")) or {}
            entries = data.get("entries", [])
        except Exception as e:
            logger.error("Failed to parse IR log: %s", e)
            findings.append(
                AuditFinding(
                    check_id="ir.triage_required",
                    severity=AuditSeverity.ERROR,
                    message=f"Invalid YAML in triage log: {e}",
                    file_path=str(log_path.relative_to(self.repo_root)),
                )
            )
            return findings

        # 3. Audit Entries
        for i, entry in enumerate(entries):
            # Entry structure validation would go here
            severity = str(entry.get("severity", "low")).lower()
            entry_id = entry.get("id", f"index_{i}")

            # Rule: ir.timeline (Required for ALL)
            if not entry.get("timeline"):
                findings.append(
                    AuditFinding(
                        check_id="ir.timeline",
                        severity=AuditSeverity.WARNING,  # Per policy
                        message=f"Incident '{entry_id}' is missing a timeline.",
                        file_path=str(log_path.relative_to(self.repo_root)),
                        context={"incident_id": entry_id},
                    )
                )

            # Conditional Rules for High/Critical
            if severity in ["high", "critical"]:
                # Rule: ir.comms
                if not entry.get("comms_log"):
                    findings.append(
                        AuditFinding(
                            check_id="ir.comms",
                            severity=AuditSeverity.WARNING,
                            message=f"High/Critical incident '{entry_id}' requires a comms log.",
                            file_path=str(log_path.relative_to(self.repo_root)),
                            context={"incident_id": entry_id, "severity": severity},
                        )
                    )

                # Rule: ir.postmortem
                if not entry.get("postmortem"):
                    findings.append(
                        AuditFinding(
                            check_id="ir.postmortem",
                            severity=AuditSeverity.WARNING,
                            message=f"High/Critical incident '{entry_id}' requires a postmortem.",
                            file_path=str(log_path.relative_to(self.repo_root)),
                            context={"incident_id": entry_id, "severity": severity},
                        )
                    )

        return findings
