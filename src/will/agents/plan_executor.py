# src/will/agents/plan_executor.py
# ID: 760cbe4e-7873-4f13-aaeb-4453785b232b

"""
Provides a refactored PlanExecutor that routes AI Agent steps through the
canonical Atomic Action system (ActionExecutor).
"""

from __future__ import annotations

from typing import Any

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError, PlannerConfig


logger = getLogger(__name__)


# ID: c87abb8b-1424-4bd5-b85b-94c013db5eeb
class PlanExecutor:
    """
    Orchestrates execution of AI-generated plans using the canonical ActionExecutor.

    This ensures that Agent actions are identical to human/CLI actions and are
    subject to the same constitutional governance.
    """

    def __init__(
        self,
        core_context: Any,  # We now require the full CoreContext
        config: PlannerConfig,
    ):
        self.config = config
        self.context = core_context
        # The ActionExecutor is the single entry point for all system changes
        self.action_executor = ActionExecutor(core_context)

    # ID: 322ea945-c32f-4f6a-8c26-640f7c38b6b3
    async def execute_plan(self, plan: list[ExecutionTask]):
        """Executes the entire plan by dispatching to the Action Gateway."""
        for i, task in enumerate(plan, 1):
            logger.info("--- Executing Step %s/%s: %s ---", i, len(plan), task.step)

            # 1. Translate legacy agent action names to the new Atomic IDs
            action_id = self._map_legacy_action(task.action)

            # 2. Extract the parameters from the AI's plan
            params = task.params.model_dump(exclude_none=True)

            # 3. Call the central Gateway
            # This handles policies, impacts, and safety checks for the AI automatically.
            result = await self.action_executor.execute(
                action_id=action_id, write=self.config.auto_commit, **params
            )

            # 4. Handle failures
            if not result.ok:
                error_msg = result.data.get("error", "Unknown error")
                raise PlanExecutionError(f"Step '{task.step}' failed: {error_msg}")

            # 5. Context Persistence: If the AI read a file, keep it in cache for the next step
            if action_id == "file.read" and "content" in result.data:
                if not hasattr(self.context, "file_content_cache"):
                    self.context.file_content_cache = {}
                self.context.file_content_cache[params["file_path"]] = result.data[
                    "content"
                ]

    def _map_legacy_action(self, legacy_name: str) -> str:
        """Translates old agent action names to the new canonical action_ids."""
        mapping = {
            "read_file": "file.read",
            "create_file": "file.create",
            "edit_file": "file.edit",
            "delete_file": "file.delete",
            "fix_docstrings": "fix.docstrings",
            "fix_headers": "fix.headers",
            "sync_db": "sync.db",
        }
        return mapping.get(legacy_name, legacy_name)
