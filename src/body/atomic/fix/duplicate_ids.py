# src/body/atomic/fix/duplicate_ids.py

"""fix.duplicate_ids — resolve duplicate UUID collisions across source files.

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
    action_id="fix.duplicate_ids",
    description="Resolve duplicate UUID collisions across source files",
    category=ActionCategory.FIX,
    policies=["rules/code/linkage"],
    remediates=["linkage.duplicate_ids"],
)
@atomic_action(
    action_id="fix.duplicate_ids",
    intent="Resolve duplicate ID conflicts by regenerating UUIDs",
    impact=ActionImpact.WRITE_METADATA,
    policies=["id_uniqueness_check"],
)
# ID: 2e7f8a1b-c3d4-4e5f-96a0-b1d2e3f4a5b6
async def action_fix_duplicate_ids(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Resolve duplicate UUID collisions in source files."""
    from body.self_healing.duplicate_id_service import fix_duplicate_ids_internal

    return await fix_duplicate_ids_internal(core_context, write=write)
