# src/core/agents/plan_executor.py
"""
Provides a clean, refactored PlanExecutor that acts as a pure orchestrator,
delegating all action-specific logic to dedicated, registered handlers.
"""

from __future__ import annotations

import asyncio
from typing import List

from core.actions.context import PlanExecutorContext
from core.actions.registry import ActionRegistry
from core.file_handler import FileHandler
from core.git_service import GitService
from features.governance.audit_context import AuditorContext
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError, PlannerConfig

log = getLogger("plan_executor")


# ID: a2b23de4-07fa-4a66-8f29-783934079956
class PlanExecutor:
    """
    A service that takes a list of ExecutionTasks and orchestrates their
    execution by dispatching them to registered ActionHandlers.
    """

    def __init__(
        self, file_handler: FileHandler, git_service: GitService, config: PlannerConfig
    ):
        """Initializes the executor with necessary dependencies."""
        self.config = config
        self.action_registry = ActionRegistry()

        # Create the shared context that all handlers will use
        self.context = PlanExecutorContext(
            file_handler=file_handler,
            git_service=git_service,
            auditor_context=AuditorContext(file_handler.repo_path),
        )

        # Pre-load the auditor's knowledge graph for performance
        asyncio.create_task(self.context.auditor_context.load_knowledge_graph())

    # ID: 65f105d2-27e4-4fca-8f96-27decc90bca5
    async def execute_plan(self, plan: List[ExecutionTask]):
        """Executes the entire plan by dispatching each task to its handler."""
        for i, task in enumerate(plan, 1):
            log.info(f"--- Executing Step {i}/{len(plan)}: {task.step} ---")

            handler = self.action_registry.get_handler(task.action)
            if not handler:
                log.warning(
                    f"Skipping task: No handler found for action '{task.action}'."
                )
                continue

            await self._execute_task_with_timeout(task, handler)

    async def _execute_task_with_timeout(self, task: ExecutionTask, handler):
        """Executes a single task with timeout protection."""
        timeout = self.config.task_timeout
        try:
            await asyncio.wait_for(
                handler.execute(task.params, self.context), timeout=timeout
            )
        except asyncio.TimeoutError:
            raise PlanExecutionError(f"Task '{task.step}' timed out after {timeout}s")
        except Exception as e:
            log.error(
                f"Error executing action '{task.action}' for step '{task.step}': {e}",
                exc_info=True,
            )
            # Re-raise as a PlanExecutionError to be caught by the execution agent
            raise PlanExecutionError(f"Step '{task.step}' failed: {e}") from e
