# src/will/agents/execution_agent.py

"""
Provides functionality for the execution_agent module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError

from will.agents.coder_agent import CodeGenerationError, CoderAgent
from will.agents.plan_executor import PlanExecutor

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


class _ExecutionAgent:
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

    # ID: ad9268be-ba8e-44b4-ac6d-b73dcaac63a1
    async def execute_plan(
        self, high_level_goal: str, plan: list[ExecutionTask]
    ) -> tuple[bool, str]:
        """
        Orchestrates the execution of a plan, delegating code generation to the CoderAgent.
        """
        if not plan:
            return (False, "Plan is empty or invalid.")
        try:
            logger.info(
                "--- Starting Governed Code Generation Phase (Orchestration) ---"
            )
            context_str = ""
            if self.executor.context.file_content_cache:
                context_str += "\n\n--- CONTEXT FROM PREVIOUS STEPS ---\n"
                for path, content in self.executor.context.file_content_cache.items():
                    context_str += f"\n--- Contents of {path} ---\n{content}\n"
                context_str += "--- END CONTEXT ---\n"

            # Phase 1: Generate Code for all steps
            for task in plan:
                if (
                    task.action
                    in ["create_file", "edit_file", "edit_function", "create_proposal"]
                    and task.params.code is None
                ):
                    logger.info(
                        f"  -> Delegating code generation for step: '{task.step}' to CoderAgent..."
                    )
                    try:
                        validated_code = (
                            await self.coder_agent.generate_and_validate_code_for_task(
                                task, high_level_goal, context_str
                            )
                        )
                        task.params.code = validated_code
                        logger.info(
                            f"  -> ✅ CoderAgent returned validated code for '{task.step}'."
                        )
                    except CodeGenerationError as e:
                        # Capture the invalid code so we can still crate it for manual fix
                        if e.code:
                            task.params.code = e.code
                            logger.warning(
                                "  -> ⚠️ Validation failed, but captured draft code for crate."
                            )

                        logger.error(f"Code generation failed: {e}")
                        raise  # Re-raise to stop execution but keep the plan modified

                    except Exception as e:
                        logger.error(
                            f"Code generation failed for step '{task.step}': {e}"
                        )
                        raise

            # Phase 2: Execute Plan
            logger.info("--- Handing off fully prepared plan to Executor ---")
            await self.executor.execute_plan(plan)
            return (True, "✅ Plan executed successfully.")

        except (PlanExecutionError, CodeGenerationError) as e:
            return (False, f"Plan execution failed: {str(e)}")
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"An unexpected error occurred during execution: {e}", exc_info=True
            )
            return (
                False,
                f"An unexpected error occurred during plan orchestration: {str(e)}",
            )
