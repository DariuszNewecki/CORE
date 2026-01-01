# src/body/atomic/crate_ops.py
# ID: atomic.crate_ops

"""
Atomic Crate Operations - Packaging logic for autonomous transactions.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionResult
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="crate.create",
    description="Package generated code into an Intent Crate for canary validation",
    category=ActionCategory.BUILD,
    policies=["body_contracts"],
    impact_level="safe",
)
# ID: 51a165f4-e0fc-405f-bee9-19c888f6c046
async def action_create_crate(
    intent: str, payload_files: dict[str, str], core_context: CoreContext, **kwargs
) -> ActionResult:
    """Atomic wrapper for the CrateCreationService."""
    start = time.time()
    try:
        from body.services.crate_creation_service import CrateCreationService

        service = CrateCreationService(core_context)
        # Call the actual packaging logic
        result = await service.create_intent_crate(
            intent=intent, payload_files=payload_files
        )

        return result  # This is already an ActionResult

    except Exception as e:
        return ActionResult(
            action_id="crate.create",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start,
        )
