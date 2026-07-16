# src/body/atomic/fix/vulture_heal.py

"""fix.vulture_heal — surgically remove Vulture-identified dead code.

Split from body/atomic/fix_actions.py (one action per module, #806).
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
    action_id="fix.vulture_heal",
    description="Surgically remove Vulture-identified dead code using LLM analysis",
    category=ActionCategory.FIX,
    policies=["dead_code"],
    remediates=["workflow.dead_code_check"],
)
@atomic_action(
    action_id="fix.vulture_heal",
    intent="Remove dead code findings via LLM",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 5a2e9c4f-1b8d-43a7-92e6-7f3c1d4b8e5a
async def action_fix_vulture_heal(
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """Surgical dead-code cleanup via the relocated body.self_healing.vulture_healer."""
    start = time.time()
    from body.self_healing.vulture_healer import heal_dead_code

    try:
        await heal_dead_code(
            context=core_context,
            file_handler=core_context.file_service,
            repo_root=core_context.git_service.repo_path,
            write=write,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.vulture_heal",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.vulture_heal",
        ok=True,
        data={"write": write},
        duration_sec=time.time() - start,
    )
