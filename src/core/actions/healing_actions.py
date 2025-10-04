# src/core/actions/healing_actions.py
"""
Action handlers for autonomous self-healing capabilities.
"""

from __future__ import annotations

from core.actions.base import ActionHandler
from core.actions.context import PlanExecutorContext
from features.self_healing.docstring_service import _async_fix_docstrings
from shared.models import TaskParams


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6e
class FixDocstringsHandler(ActionHandler):
    """Handles the 'autonomy.self_healing.fix_docstrings' action."""

    @property
    # ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6f7a
    def name(self) -> str:
        """Return the unique identifier for this self-healing module."""
        return "autonomy.self_healing.fix_docstrings"

    # ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8b
    async def execute(self, params: TaskParams, context: PlanExecutorContext):
        """
        Executes the docstring fixing logic by calling the dedicated service.
        This action does not run in dry-run mode; it always applies changes.
        """
        await _async_fix_docstrings(dry_run=False)
