# src/mind/logic/engines/cli_gate/checks/help_required.py

"""Verifies cli.help_required: every command MUST surface a non-empty
help summary (either via @command_meta or a docstring Typer can lift).
"""

from __future__ import annotations

from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# Matches rule_executor._map_enforcement_to_severity for reporting-level
# rules (cli.help_required). The executor overrides at dispatch; this keeps
# direct callers (unit tests, smoke checks) seeing the truthful value.
# Per ADR-098 D4 / #606.
_DEFAULT_FINDING_SEVERITY = AuditSeverity.INFO


# ID: 7db1d368-f633-46ac-99c2-d492c040f402
class HelpRequiredCheck(CliCheck):
    check_type = "help_required"

    # ID: b3085b57-5870-44be-a264-82ab6bf4a23e
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for cmd in commands:
            summary = (cmd.get("summary") or "").strip()
            if summary:
                continue
            name = cmd.get("name") or "<unknown>"
            findings.append(
                AuditFinding(
                    check_id="cli_gate.help_required",
                    severity=_DEFAULT_FINDING_SEVERITY,
                    message=(
                        f"Command '{name}' has no help summary (docstring "
                        "or @command_meta(summary=...) required)."
                    ),
                    file_path=cmd.get("file_path") or "none",
                    context={"command_name": name},
                )
            )

        return findings
