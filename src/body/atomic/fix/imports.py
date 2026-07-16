# src/body/atomic/fix/imports.py

"""fix.imports — sort and group Python imports via Ruff.

Split from body/atomic/fix_actions.py (one action per module, #806).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="fix.imports",
    description="Sort and group imports according to PEP 8 / Constitutional standards",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["style.import_order", "style.no_unused_imports"],
)
@atomic_action(
    action_id="fix.imports",
    intent="Standardize Python import blocks using Ruff",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: d5879178-fdfe-4d8b-b6a6-f887f8e9500b
async def action_fix_imports(
    core_context: CoreContext | None = None, write: bool = False, **kwargs
) -> ActionResult:
    """Sort and group Python imports according to constitutional style policy.

    Runs ruff inside the execution context's repo_path so an in-worktree
    flow execution (ADR-106) sorts imports in the sandbox tree, not the
    real one (#638). A None context falls back to the process cwd.
    """
    start = time.time()
    from shared.utils.subprocess_utils import run_poetry_command

    cwd = (
        core_context.git_service.repo_path
        if core_context is not None and core_context.git_service is not None
        else None
    )
    target_path = "src/"
    try:
        cmd = ["ruff", "check", target_path, "--select", "I"]
        if write:
            cmd.append("--fix")
        cmd.append("--exit-zero")

        run_poetry_command(f"Sorting imports in {target_path}", cmd, cwd=cwd)

        return ActionResult(
            action_id="fix.imports",
            ok=True,
            data={"status": "completed", "target": target_path, "write": write},
            duration_sec=time.time() - start,
        )
    except Exception as e:
        logger.error("fix.imports failed: %s", e, exc_info=True)
        return ActionResult(
            action_id="fix.imports",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
