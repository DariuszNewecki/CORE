# src/mind/logic/engines/cli_gate/checks/no_layer_exposure.py

"""Verifies cli.no_layer_exposure: resource segment of canonical name
must not name an internal architectural layer or legacy verb-namespace.
"""

from __future__ import annotations

from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# ID: f52a1c6e-804d-43c0-ab57-d6d1b0294cd0
class NoLayerExposureCheck(CliCheck):
    check_type = "no_layer_exposure"

    # ID: 2e5d438f-7d3b-4079-9862-316f1bfadaf6
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        forbidden = set(params.get("forbidden_resources") or [])
        findings: list[AuditFinding] = []

        for cmd in commands:
            name = cmd.get("name") or ""
            if not name:
                continue
            resource = name.split(".", 1)[0]
            if resource in forbidden:
                findings.append(
                    AuditFinding(
                        check_id="cli_gate.no_layer_exposure",
                        severity=AuditSeverity.BLOCK,
                        message=(
                            f"Command '{name}' exposes forbidden resource "
                            f"'{resource}'."
                        ),
                        file_path=cmd.get("file_path") or "none",
                        context={
                            "command_name": name,
                            "resource": resource,
                            "forbidden_resources": sorted(forbidden),
                        },
                    )
                )

        return findings
