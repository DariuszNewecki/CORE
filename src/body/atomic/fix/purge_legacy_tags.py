# src/body/atomic/fix/purge_legacy_tags.py

"""fix.purge_legacy_tags — remove obsolete tag formats.

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
    action_id="fix.purge_legacy_tags",
    description="Remove obsolete tag formats (e.g. legacy '# owner:', '# Tag:' lines)",
    category=ActionCategory.FIX,
    policies=["tag_hygiene"],
    remediates=["metadata.no_legacy_tags"],
)
@atomic_action(
    action_id="fix.purge_legacy_tags",
    intent="Remove legacy tag formats from source files",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: 3c8d2f15-7e94-4a6b-b1c5-9d3f7e2a4b8d
async def action_fix_purge_legacy_tags(
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """Wrap body.self_healing.purge_legacy_tags_service.purge_legacy_tags."""
    start = time.time()
    from body.self_healing.purge_legacy_tags_service import purge_legacy_tags

    try:
        removed = await purge_legacy_tags(core_context, dry_run=not write)
    except Exception as e:
        return ActionResult(
            action_id="fix.purge_legacy_tags",
            ok=False,
            data={"error": str(e), "write": write},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.purge_legacy_tags",
        ok=True,
        data={"removed": removed, "write": write},
        duration_sec=time.time() - start,
    )
