# src/body/atomic/fix/capability_tagging.py

"""fix.capability_tagging — tag untagged capabilities via LLM naming.

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
    action_id="fix.capability_tagging",
    description="Tag untagged public capabilities using LLM-suggested names",
    category=ActionCategory.FIX,
    policies=["capability_tagging"],
    remediates=["symbols.capability_required"],
)
@atomic_action(
    action_id="fix.capability_tagging",
    intent="Tag untagged capabilities via LLM",
    impact=ActionImpact.WRITE_METADATA,
    policies=["atomic_actions"],
)
# ID: 7b3c8d51-9e2a-4f7b-a1e6-5c4d8b2f9a3e
async def action_fix_capability_tagging(
    core_context: CoreContext,
    write: bool = False,
    limit: int = 0,
    **kwargs,
) -> ActionResult:
    """Tag untagged capabilities via the will-layer naming agent.

    Delegates to ``core_context.capability_tagging_service`` — a Body-layer
    facade wired at the composition root (ADR-064 closure).  No will.* import
    exists in this file; the cross-layer dependency is injected, not imported.
    """
    start = time.time()
    if core_context.cognitive_service is None:
        return ActionResult(
            action_id="fix.capability_tagging",
            ok=False,
            data={
                "error": "cognitive_service not available",
                "write": write,
                "limit": limit,
            },
            duration_sec=0.0,
        )
    if core_context.capability_tagging_service is None:
        return ActionResult(
            action_id="fix.capability_tagging",
            ok=False,
            data={
                "error": "capability_tagging_service not initialized — composition root must wire it",
                "write": write,
                "limit": limit,
            },
            duration_sec=0.0,
        )
    from shared.infrastructure.database.session_manager import get_session

    try:
        await core_context.capability_tagging_service.run(
            session_factory=get_session,
            cognitive_service=core_context.cognitive_service,
            knowledge_service=core_context.knowledge_service,
            write=write,
            dry_run=not write,
            limit=limit,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.capability_tagging",
            ok=False,
            data={"error": str(e), "write": write, "limit": limit},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.capability_tagging",
        ok=True,
        data={"write": write, "limit": limit},
        duration_sec=time.time() - start,
    )
