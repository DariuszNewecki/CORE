# src/features/autonomy/autonomous_developer.py
# ID: features.autonomy.autonomous_developer

"""
Autonomous Developer - Constitutional Workflow Interface

MIGRATED TO V2: This now wraps the new constitutional workflow system.
Uses dynamic phase composition based on .intent/workflows/ definitions.
"""

from __future__ import annotations

from typing import Any

from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: legacy-wrapper-for-v2
# ID: 4e864475-0bb5-42d9-ba26-fff85955a3d6
async def develop_from_goal(
    session: Any,  # Kept for backward compatibility
    context: CoreContext,
    goal: str,
    task_id: str | None = None,
    output_mode: str = "direct",
    write: bool = False,
) -> tuple[bool, str]:
    """
    Legacy interface - automatically infers workflow type from goal.

    MIGRATION NOTE: New code should use develop_from_goal_v2 with explicit workflow_type.
    This wrapper provides backward compatibility during transition.

    Args:
        session: Database session (kept for compatibility, not used)
        context: CoreContext with services
        goal: High-level objective
        task_id: Optional task tracking ID
        output_mode: Output mode (kept for compatibility)
        write: Whether to apply changes

    Returns:
        (success, message) tuple
    """
    from features.autonomy.autonomous_developer_v2 import (
        develop_from_goal_v2,
        infer_workflow_type,
    )

    # Auto-infer workflow type from goal text
    workflow_type = infer_workflow_type(goal)

    logger.info("🔄 Legacy interface: Inferred workflow '%s' from goal", workflow_type)
    logger.info("💡 TIP: Use develop_from_goal_v2() with explicit workflow_type")

    return await develop_from_goal_v2(
        context=context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        task_id=task_id,
    )
