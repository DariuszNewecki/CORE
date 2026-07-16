# src/body/atomic/fix/format_code.py

"""fix.format — format code with ruff format and ruff check.

Split from body/atomic/fix_actions.py (one action per module, #806).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="fix.format",
    description="Format code with ruff format and ruff check",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["style.formatter_required", "workflow.ruff_format_check"],
)
@atomic_action(
    action_id="fix.format",
    intent="Atomic action for action_format_code",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5c3ede6c-23e1-4b92-8a00-7b2046eac121
async def action_format_code(
    core_context: CoreContext | None = None,
    file_path: str | None = None,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """Format code using ruff format and ruff check.

    Runs ruff inside the execution context's repo_path so that when the
    action executes within a hermetic flow worktree (ADR-106) the format
    pass operates on the sandbox tree, not the real one (#638). A None
    context (defensive / non-executor path) falls back to the process cwd.
    """
    start = time.time()
    from body.self_healing.code_style_service import format_code

    cwd = (
        core_context.git_service.repo_path
        if core_context is not None and core_context.git_service is not None
        else None
    )
    # Graceful skip when the target file is absent from the sandbox worktree.
    # Happens when audit detected a style violation on an uncommitted file and
    # the sandbox (git worktree at HEAD) doesn't have it yet. Returning ok=True
    # prevents premature cap exhaustion; the sensor re-fires post-commit and the
    # next proposal succeeds against the committed file. (ADR-071 D2.2 / #660)
    if file_path is not None and cwd is not None:
        resolved = Path(str(cwd)) / file_path
        if not resolved.exists():
            return ActionResult(
                action_id="fix.format",
                ok=True,
                data={
                    "skipped": True,
                    "reason": "file_not_in_sandbox",
                    "file_path": file_path,
                    "write": write,
                },
                duration_sec=time.time() - start,
            )
    try:
        format_code(path=file_path, write=write, cwd=cwd)
    except Exception as e:
        logger.error("fix.format failed on %s: %s", file_path, e, exc_info=True)
        return ActionResult(
            action_id="fix.format",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.format",
        ok=True,
        data={"formatted": True, "write": write},
        duration_sec=time.time() - start,
    )
