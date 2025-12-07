# src/mind/governance/checks/ir_check.py
"""
Enforces ir.comms, ir.postmortem, ir.timeline: Each must have dedicated log entry.
"""

from __future__ import annotations

from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 25dc2724-9d94-4ba5-a1cd-c7d93a910d41
class IRCheck(BaseCheck):
    policy_rule_ids = ["ir.comms", "ir.postmortem", "ir.timeline"]

    _REQUIRED = {
        "ir.comms": "COMMS_LOG",
        "ir.postmortem": "POSTMORTEM",
        "ir.timeline": "TIMELINE",
    }

    # ID: a0569012-da63-4912-9a1b-ba1c4e9afd4e
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        log_path = Path(".core/ir.log")

        if not log_path.exists():
            for rule_id in self.policy_rule_ids:
                findings.append(self._missing_log(rule_id, log_path))
            return findings

        content = log_path.read_text(encoding="utf-8").upper()

        for rule_id, marker in self._REQUIRED.items():
            if marker not in content:
                findings.append(self._missing_log(rule_id, log_path, marker))

        return findings

    def _missing_log(
        self, rule_id: str, log_path: Path, marker: str | None = None
    ) -> AuditFinding:
        msg = "Missing IR log entry"
        if marker:
            msg += f" for `{marker}`"
        msg += ". Run `fix ir-log`."
        return AuditFinding(
            check_id=rule_id,
            severity=AuditSeverity.WARNING,
            message=msg,
            file_path=".core/ir.log",
            line_number=1,
        )
