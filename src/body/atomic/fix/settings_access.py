# src/body/atomic/fix/settings_access.py

"""fix.settings_access — refactor settings.* imports to DI via CoreContext.

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
    action_id="fix.settings_access",
    description="Refactor settings.* imports to dependency injection via CoreContext",
    category=ActionCategory.FIX,
    policies=["dependency_injection"],
    remediates=["architecture.body.no_settings_import"],
)
@atomic_action(
    action_id="fix.settings_access",
    intent="Refactor settings imports to DI via CoreContext",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 9e8d2c1f-3a6b-4d57-b9e2-1f4a8c5d3e0b
async def action_fix_settings_access(
    core_context: CoreContext,
    write: bool = False,
    layers: list[str] | None = None,
    **kwargs,
) -> ActionResult:
    """Refactor settings imports to dependency injection across given layers.

    Wraps body.maintenance.refactor_settings_access; translates the
    atomic-action convention (`write`) to the wrapped function's
    (`dry_run = not write`), passes repo_path from CoreContext, and
    surfaces the per-layer summary on data.results.
    """
    start = time.time()
    from body.maintenance.refactor_settings_access import refactor_settings_access

    try:
        results = await refactor_settings_access(
            repo_path=core_context.git_service.repo_path,
            layers=layers,
            dry_run=not write,
        )
    except Exception as e:
        return ActionResult(
            action_id="fix.settings_access",
            ok=False,
            data={"error": str(e), "write": write, "layers": layers},
            duration_sec=time.time() - start,
        )
    return ActionResult(
        action_id="fix.settings_access",
        ok=True,
        data={"results": results, "write": write, "layers": layers},
        duration_sec=time.time() - start,
    )
