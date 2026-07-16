# src/body/atomic/fix/headers.py

"""fix.headers — fix file headers to constitutional standards.

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
    action_id="fix.headers",
    description="Fix file headers to match constitutional standards",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["layout.src_module_header"],
)
@atomic_action(
    action_id="fix.headers",
    intent="Atomic action for action_fix_headers",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 7d43d782-739a-47d3-ae3e-c36047ad9867
async def action_fix_headers(
    core_context: CoreContext, write: bool = False, **kwargs
) -> ActionResult:
    """Fix file headers."""
    from body.self_healing.header_service import fix_headers_internal

    return await fix_headers_internal(core_context, write=write)
