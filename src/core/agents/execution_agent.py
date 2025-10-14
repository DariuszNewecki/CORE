# src/core/agents/execution_agent.py
"""
Provides functionality for the execution_agent module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agents.coder_agent import CoderAgent
from core.agents.plan_executor import PlanExecutor
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError

if TYPE_CHECKING:
    from features.governance.audit_context import AuditorContext

log = getLogger("execution_agent")


# ID: 1fedacd4-8227-4216-b07a-c807bd450550
class ExecutionAgent:
    """Orchestrates the execution of a plan, delegating code generation to the CoderAgent."""

    def __init__(
        self,
        coder_agent: CoderAgent,
        plan_executor: PlanExecutor,
        auditor_context: AuditorContext,
    ):
        """Initializes the ExecutionAgent as a pure orchestrator."""
        self.coder_agent = coder_agent
        self.executor = plan_executor
        self.auditor_context = auditor_context

    # ID: 6557eefd-2f5e-4904-998a-e7ad2d8d070f
    async def execute_plan(
        self, high_level_goal: str, plan: list[ExecutionTask]
    ) -> tuple[bool, str]:
        """
        Orchestrates the execution of a plan, delegating code generation to the CoderAgent.
        """
        if not plan:
            return False, "Plan is empty or invalid."

        try:
            log.info("--- Starting Governed Code Generation Phase (Orchestration) ---")

            # Prepare context from previously executed steps (e.g., read_file)
            context_str = ""
            if self.executor.context.file_content_cache:
                context_str += "\n\n--- CONTEXT FROM PREVIOUS STEPS ---\n"
                for path, content in self.executor.context.file_content_cache.items():
                    context_str += f"\n--- Contents of {path} ---\n{content}\n"
                context_str += "--- END CONTEXT ---\n"

            for task in plan:
                if (
                    task.action
                    in ["create_file", "edit_file", "edit_function", "create_proposal"]
                    and task.params.code is None
                ):
                    log.info(
                        f"  -> Delegating code generation for step: '{task.step}' to CoderAgent..."
                    )
                    validated_code = (
                        await self.coder_agent.generate_and_validate_code_for_task(
                            task, high_level_goal, context_str
                        )
                    )
                    task.params.code = validated_code
                    log.info(
                        f"  -> ✅ CoderAgent returned validated code for '{task.step}'."
                    )

            log.info("--- Handing off fully prepared plan to Executor ---")
            await self.executor.execute_plan(plan)
            return True, "✅ Plan executed successfully."

        except PlanExecutionError as e:
            return False, f"Plan execution failed during orchestration: {str(e)}"
        except Exception as e:
            log.error(
                f"An unexpected error occurred during execution: {e}", exc_info=True
            )
            return (
                False,
                f"An unexpected error occurred during plan orchestration: {str(e)}",
            )
