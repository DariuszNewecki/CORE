# src/core/actions/validation_actions.py
"""
Action handlers for validation and verification tasks.
"""

from __future__ import annotations

from core.actions.base import ActionHandler
from core.actions.context import PlanExecutorContext
from shared.logger import getLogger
from shared.models import TaskParams

log = getLogger("validation_actions")


# ID: a4e534f9-b6a0-4151-a3ee-9c2fcc0ec87f
class ValidateCodeHandler(ActionHandler):
    """A handler for the 'core.validation.validate_code' action."""

    @property
    # ID: 29a5f80d-3a24-4d06-a1ad-0403c376319b
    def name(self) -> str:
        return "core.validation.validate_code"

    # ID: 38c34fa0-6443-46ee-a636-e18a28fb0a81
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """This is a no-op as validation is performed before execution."""
        log.info(
            "Step 'core.validation.validate_code' acknowledged. Pre-flight validation already completed."
        )
        # This action does nothing because the real validation happens
        # in the `micro_apply` command's pre-flight check.
        pass
