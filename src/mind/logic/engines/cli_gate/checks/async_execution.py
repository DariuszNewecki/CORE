# src/mind/logic/engines/cli_gate/checks/async_execution.py

"""Verifies cli.async_execution: every async Typer callback MUST be
wrapped with the @core_command decorator.

The decorator records each wrapped function in ``COMMAND_REGISTRY``
keyed by the original ``func.__name__``; ``functools.wraps`` preserves
``__name__`` on the returned wrapper. A correctly-wrapped async command
therefore presents to Typer as a *sync* callback (the wrapper) whose
name is in the registry. A bare async callback — coroutine function
whose name is NOT in the registry — is the violation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 933a93fd-eb5a-4909-a514-688cb8d8a43e
class AsyncExecutionCheck(CliCheck):
    check_type = "async_execution"

    # ID: 913248ba-1bfb-4c06-837d-30631ff978b9
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        from cli.utils.decorators import COMMAND_REGISTRY

        required_decorator = params.get("required_decorator") or "core_command"
        findings: list[AuditFinding] = []

        for cmd in commands:
            callback = cmd.get("callback")
            if callback is None:
                continue
            if not asyncio.iscoroutinefunction(callback):
                continue
            cb_name = getattr(callback, "__name__", "")
            if cb_name in COMMAND_REGISTRY:
                continue

            name = cmd.get("name") or cb_name or "<unknown>"
            findings.append(
                AuditFinding(
                    check_id="cli_gate.async_execution",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"Async command '{name}' is missing the "
                        f"@{required_decorator} decorator — event-loop "
                        "execution is undefined without it."
                    ),
                    file_path=cmd.get("file_path") or "none",
                    context={
                        "command_name": name,
                        "callback_name": cb_name,
                        "required_decorator": required_decorator,
                    },
                )
            )

        return findings
