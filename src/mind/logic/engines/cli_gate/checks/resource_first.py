# src/mind/logic/engines/cli_gate/checks/resource_first.py

"""Verifies cli.resource_first: 'resource action [flags]' command shape.

Depth is computed from the canonical dotted name and bounded between
``min_depth`` and ``max_depth`` inclusive (defaults 2 and 3). Depth-3
is the depth a real sub-hub nesting produces (resource.subresource.action);
deeper paths remain blocked by design.
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
        min_depth = int(params.get("min_depth", 2))
        max_depth = int(params.get("max_depth", 3))
        findings: list[AuditFinding] = []

        for cmd in commands:
            name = cmd.get("name") or ""
            if not name:
                continue
            parts = name.split(".")
            depth = len(parts)
            if min_depth <= depth <= max_depth:
                continue

            findings.append(
                AuditFinding(
                    check_id="cli_gate.resource_first",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"Command '{name}' has depth {depth}; "
                        f"must be between {min_depth} and {max_depth}."
                    ),
                    file_path=cmd.get("file_path") or "none",
                    context={
                        "command_name": name,
                        "depth": depth,
                        "min_depth": min_depth,
                        "max_depth": max_depth,
                    },
                )
            )

        return findings
