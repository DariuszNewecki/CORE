# src/body/atomic/fix/logging_fix.py

"""fix.logging — replace print statements with proper logging.

Split from body/atomic/fix_actions.py (one action per module, #806).
Module named logging_fix (not logging) to avoid any tooling confusion
with the stdlib module.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action


if TYPE_CHECKING:
    from shared.context import CoreContext


@register_action(
    action_id="fix.logging",
    description="Replace print statements with proper logging",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=[
        "logic.logging.standard_only",
        "architecture.channels.logic_no_terminal_rendering",
    ],
)
@atomic_action(
    action_id="fix.logging",
    intent="Atomic action for action_fix_logging",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 7661f20f-3d41-4501-a0ab-c30804d29ad0
async def action_fix_logging(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix logging violations."""
    start = time.time()
    from body.self_healing.logging_service import LoggingFixer

    if core_context.file_handler is None:
        return ActionResult(
            action_id="fix.logging",
            ok=False,
            data={"error": "file_handler not initialized"},
            duration_sec=time.time() - start,
        )
    fixer = LoggingFixer(
        repo_root=core_context.git_service.repo_path,
        file_handler=core_context.file_handler,
        dry_run=not write,
    )
    try:
        result = fixer.fix_all()
    except Exception as e:
        return ActionResult(
            action_id="fix.logging",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.logging",
        ok=True,
        data=result,
        duration_sec=time.time() - start,
    )
