# src/will/agents/plan_executor.py

"""
Provides a clean, refactored PlanExecutor that acts as a pure orchestrator,
delegating all action-specific logic to dedicated, registered handlers.
"""

from __future__ import annotations

import asyncio

from body.actions.context import PlanExecutorContext
from body.actions.registry import ActionRegistry
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.git_service import GitService
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError, PlannerConfig


logger = getLogger(__name__)


# ID: c87abb8b-1424-4bd5-b85b-94c013db5eeb
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
        self.context = PlanExecutorContext(
            file_handler=file_handler,
            git_service=git_service,
            auditor_context=AuditorContext(file_handler.repo_path),
        )
        self._knowledge_graph_task = asyncio.create_task(
            self.context.auditor_context.load_knowledge_graph()
        )

    # ID: 322ea945-c32f-4f6a-8c26-640f7c38b6b3
    async def execute_plan(self, plan: list[ExecutionTask]):
        """Executes the entire plan by dispatching each task to its handler."""
        for i, task in enumerate(plan, 1):
            logger.info("--- Executing Step %s/{len(plan)}: {task.step} ---", i)
            handler = self.action_registry.get_handler(task.action)
            if not handler:
                logger.warning(
                    "Skipping task: No handler found for action '%s'.", task.action
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
        except TimeoutError:
            raise PlanExecutionError(f"Task '{task.step}' timed out after {timeout}s")
        except Exception as e:
            logger.error(
                "Error executing action '%s' for step '%s': %s",
                task.action,
                task.step,
                e,
                exc_info=True,
            )
            raise PlanExecutionError(f"Step '{task.step}' failed: {e}") from e
