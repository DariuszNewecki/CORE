# src/mind/logic/engines/cli_gate/checks/resource_first.py

"""Verifies cli.resource_first: 'resource action [flags]' command shape.

Depth is computed from the canonical dotted name. Commands at the
``admin`` namespace may use a deeper structure (``admin.<group>.<verb>``)
per the rule's exception clause.
"""

from __future__ import annotations

from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# ID: c7ab8f96-5ab7-4894-acb2-58aa4735dcbf
class ResourceFirstCheck(CliCheck):
    check_type = "resource_first"

    # ID: 63dfc01c-b9a8-453b-a7e7-96d6fe7d039b
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        expected_depth = int(params.get("expected_depth", 2))
        admin_depth = int(params.get("admin_namespace_depth", 3))
        findings: list[AuditFinding] = []

        for cmd in commands:
            name = cmd.get("name") or ""
            if not name:
                continue
            parts = name.split(".")
            depth = len(parts)
            resource = parts[0] if parts else ""
            allowed = (depth == expected_depth) or (
                resource == "admin" and depth == admin_depth
            )
            if allowed:
                continue

            findings.append(
                AuditFinding(
                    check_id="cli_gate.resource_first",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"Command '{name}' has depth {depth}; resource-first "
                        f"requires depth {expected_depth} "
                        f"(admin namespace may use depth {admin_depth})."
                    ),
                    file_path=cmd.get("file_path") or "none",
                    context={
                        "command_name": name,
                        "depth": depth,
                        "expected_depth": expected_depth,
                        "admin_namespace_depth": admin_depth,
                    },
                )
            )

        return findings
