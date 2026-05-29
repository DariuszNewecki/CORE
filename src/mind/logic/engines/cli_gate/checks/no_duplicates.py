# src/mind/logic/engines/cli_gate/checks/no_duplicates.py

"""Verifies cli.command.no_duplicates: every command canonical name MUST
be registered exactly once. The runtime first-wins dedup in
``_sync_commands_to_db`` keeps the DB consistent; this check surfaces
the duplicates audit-time so they can be remediated rather than
silently dropped.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# ID: b2efaea9-5149-41cd-b320-a68d4f68befa
class NoDuplicatesCheck(CliCheck):
    check_type = "no_duplicates"

    # ID: dad546ee-04f8-493b-bf87-6e5bae28c157
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for cmd in commands:
            name = cmd.get("name")
            if name:
                by_name[name].append(cmd)

        findings: list[AuditFinding] = []
        for name, group in by_name.items():
            if len(group) <= 1:
                continue
            locations = [c.get("file_path") or "unknown" for c in group]
            entrypoints = [c.get("entrypoint") or "unknown" for c in group]
            findings.append(
                AuditFinding(
                    check_id="cli_gate.no_duplicates",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"Command '{name}' is registered {len(group)} times "
                        f"({', '.join(entrypoints)})."
                    ),
                    file_path=locations[0],
                    context={
                        "command_name": name,
                        "registration_count": len(group),
                        "entrypoints": entrypoints,
                        "file_paths": locations,
                    },
                )
            )

        return findings
