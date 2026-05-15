# src/cli/commands/fix/code_style.py
"""
Code style and formatting commands for the 'fix' CLI group.

Provides:
- fix headers (file header compliance)

CONSTITUTIONAL ALIGNMENT:
- Logic decoupled from CLI helpers to prevent circular imports.
- Mutation logic remains in 'internal' functions for Atomic Action use.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer

# DEPRECATED: fix_headers_internal moved to body/self_healing/header_service.py
# under ADR-050. This re-export keeps in-CLI callers working; remove after the
# CLI migration epic completes.
from body.self_healing.header_service import fix_headers_internal
from cli.utils import core_command
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action

from . import fix_app


__all__ = ["fix_headers_cmd", "fix_headers_internal"]


@fix_app.command(
    "headers", help="Ensures all files have constitutionally compliant headers."
)
@core_command(dangerous=True, confirmation=True)
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for fix_headers_cmd",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 0077efbb-9090-42bb-a602-2ff3b7853875
async def fix_headers_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to files with violations."
    ),
) -> ActionResult:
    """
    CLI wrapper for fix headers command.
    """
    with logger.info("[cyan]Checking file headers...[/cyan]"):
        return await fix_headers_internal(ctx.obj, write=write)
