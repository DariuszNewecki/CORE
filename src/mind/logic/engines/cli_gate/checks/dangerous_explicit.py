# src/mind/logic/engines/cli_gate/checks/dangerous_explicit.py

"""Verifies cli.dangerous_explicit: commands declared as mutating MUST
both flag ``dangerous=True`` AND expose a ``write`` parameter so that
the @core_command decorator can short-circuit into dry-run by default.
"""

from __future__ import annotations

from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 50265728-e4df-4ac3-985a-bedfb159bdd0
class DangerousExplicitCheck(CliCheck):
    check_type = "dangerous_explicit"

    # ID: efba7c6c-6a1c-4200-9769-6580c2450b23
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for cmd in commands:
            if cmd.get("behavior") != "mutate":
                continue

            name = cmd.get("name") or ""
            file_path = cmd.get("file_path") or "none"

            if not cmd.get("dangerous"):
                findings.append(
                    AuditFinding(
                        check_id="cli_gate.dangerous_explicit",
                        severity=AuditSeverity.BLOCK,
                        message=(
                            f"Mutating command '{name}' is not marked "
                            "dangerous=True."
                        ),
                        file_path=file_path,
                        context={"command_name": name, "missing": "dangerous"},
                    )
                )

            if "write" not in (cmd.get("params_list") or []):
                findings.append(
                    AuditFinding(
                        check_id="cli_gate.dangerous_explicit",
                        severity=AuditSeverity.BLOCK,
                        message=(
                            f"Mutating command '{name}' is missing the "
                            "mandatory 'write' parameter."
                        ),
                        file_path=file_path,
                        context={"command_name": name, "missing": "write_param"},
                    )
                )

        return findings
