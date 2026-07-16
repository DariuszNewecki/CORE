# src/body/atomic/fix/ids.py

"""fix.ids — add missing ID tags to functions and classes.

Split from body/atomic/fix_actions.py (one action per module, #806).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action


if TYPE_CHECKING:
    from shared.context import CoreContext


@register_action(
    action_id="fix.ids",
    description="Add missing ID tags to functions and classes",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["purity.stable_id_anchor", "linkage.assign_ids"],
)
@atomic_action(
    action_id="fix.ids",
    intent="Atomic action for action_fix_ids",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 854f5010-aaec-4f14-8d72-3e3070334c54
async def action_fix_ids(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix missing ID tags."""
    from body.self_healing.id_tagging_service import fix_ids_internal

    return await fix_ids_internal(core_context, write=write)
