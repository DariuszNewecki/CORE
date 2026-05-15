# src/cli/commands/fix/atomic_actions.py
"""
Fix atomic actions pattern violations.
Thin CLI shell delegating to body.atomic.fix_actions.
Upgraded to V2.1: Now manages mandatory imports.

CONSTITUTIONAL ALIGNMENT:
- Removed legacy error decorators to prevent circular imports.
- Routes all healing logic through the ActionExecutor gateway.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer

from body.atomic.executor import ActionExecutor

# DEPRECATED: _fix_file_violations and its private helpers moved to
# body/self_healing/atomic_actions_fixer.py under ADR-050. The function was
# renamed to fix_file_violations (no leading underscore) to match body's
# public-API convention. This re-export keeps any remaining external callers
# working; remove after the CLI migration epic completes.
from body.self_healing.atomic_actions_fixer import fix_file_violations
from cli.utils import core_command
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action

from . import fix_app


__all__ = ["fix_atomic_actions_cmd", "fix_file_violations"]


@fix_app.command("atomic-actions", help="Fix atomic actions pattern violations.")
@core_command(dangerous=True, confirmation=False)
@atomic_action(
    action_id="fix.cli.atomic_actions",
    intent="CLI entry point to heal atomic action violations",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: d729c8ff-0b0c-4873-85b6-0b8151a4265c
async def fix_atomic_actions_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply fixes."),
) -> ActionResult:
    """
    CLI Wrapper: Delegates to fix.atomic_actions via ActionExecutor.
    """
    core_context = ctx.obj
    executor = ActionExecutor(core_context)
    with logger.info("[cyan]Healing atomic actions...[/cyan]"):
        result = await executor.execute("fix.atomic_actions", write=write)
    return result
