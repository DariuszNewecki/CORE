# src/mind/logic/engines/cli_gate/checks/standard_verbs.py

"""Verifies cli.standard_verbs: action segment of canonical name should
come from the approved verb vocabulary. Reporting-level rule.
"""

from __future__ import annotations

from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# ID: dea77503-0ced-42c9-b114-3d3042828545
class StandardVerbsCheck(CliCheck):
    check_type = "standard_verbs"

    # ID: 1c89b704-2e0b-45a7-b077-3997a9b64443
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        allowed = set(params.get("allowed_verbs") or [])
        if not allowed:
            return []

        findings: list[AuditFinding] = []

        for cmd in commands:
            name = cmd.get("name") or ""
            parts = name.split(".")
            if len(parts) < 2:
                continue
            action = parts[1]
            if action in allowed:
                continue
            findings.append(
                AuditFinding(
                    check_id="cli_gate.standard_verbs",
                    severity=AuditSeverity.BLOCK,
                    message=(f"Command '{name}' uses non-standard verb '{action}'."),
                    file_path=cmd.get("file_path") or "none",
                    context={
                        "command_name": name,
                        "action": action,
                    },
                )
            )

        return findings
