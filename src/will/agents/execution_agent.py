# src/will/agents/execution_agent.py

"""
The ExecutionAgent (Contractor): Executes validated code blueprints.

FIXED: Now skips steps that failed code generation instead of trying to execute them.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.action_types import ActionResult
from shared.logger import getLogger
from shared.models.workflow_models import ExecutionResults
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from body.atomic.executor import ActionExecutor
    from shared.models import DetailedPlan, DetailedPlanStep

logger = getLogger(__name__)


# ID: 4b9a28f4-6c4d-4a5e-8f7c-9d0e1b2a3c4d
class ExecutionAgent:
    """
    The Contractor: Executes validated code blueprints.

    FIXED: Skips steps that failed code generation.
    """

    def __init__(self, executor: ActionExecutor):
        """
        Initialize the ExecutionAgent.

        Args:
            executor: The ActionExecutor (The Body's Gateway).
        """
        self.executor = executor
        self.tracer = DecisionTracer()

        logger.info("ExecutionAgent initialized (Contractor Mode)")

    # ID: b2c3d4e5-f678-90ab-cdef-0123456789ab
    async def execute_plan(
        self,
        detailed_plan: DetailedPlan,
    ) -> ExecutionResults:
        """
        Execute a DetailedPlan step-by-step.

        This assumes the plan has already passed a Canary Trial in the sandbox.
        """
        start_time = time.time()

        logger.info(
            "🏗️ Construction Phase: Applying %d spec-validated steps...",
            detailed_plan.step_count,
        )

        results: list[ActionResult] = []
        success_count = 0
        failure_count = 0
        aborted_at_step: int | None = None

        for i, step in enumerate(detailed_plan.steps, 1):
            logger.info(
                "  [Step %d/%d] Executing: %s...",
                i,
                detailed_plan.step_count,
                step.description,
            )

            # FIXED: Skip steps that failed code generation
            if step.metadata.get("generation_failed", False):
                error_msg = step.metadata.get("error", "Code generation failed")
                logger.warning(
                    "    → ⚠️ Skipping step - code generation failed: %s", error_msg
                )
                result = ActionResult(
                    action_id=step.action,
                    ok=False,
                    data={
                        "error": error_msg,
                        "error_type": "CodeGenerationFailed",
                        "skipped": True,
                    },
                    duration_sec=0.0,
                )
                results.append(result)
                failure_count += 1

                # Mark as critical to stop execution
                if step.is_critical:
                    aborted_at_step = i
                    logger.error(
                        "⛔ Critical step failed during generation. Aborting construction."
                    )
                    break

                continue

            # Execution via Constitutional Gateway
            result = await self._execute_step(step, step_number=i)
            results.append(result)

            if result.ok:
                success_count += 1
                logger.info("    → ✅ Applied successfully.")
            else:
                failure_count += 1
                error = result.data.get("error", "Unknown error")
                logger.error("    → ❌ Step failed: %s", error)

                # CONSTITUTIONAL SAFETY: Abort on critical failure to prevent corruption
                if step.is_critical:
                    aborted_at_step = i
                    logger.error(
                        "⛔ Critical step failed. Aborting construction for safety."
                    )
                    break

        duration = time.time() - start_time

        # Final Summary for the result object
        metadata = {
            "completed_successfully": failure_count == 0,
            "total_duration_sec": duration,
        }

        if aborted_at_step is not None:
            metadata["aborted_at_step"] = aborted_at_step
            metadata["abort_reason"] = "Critical step failure"

        logger.info(
            "🏁 Execution Result: %s (%d success, %d failure) in %.2fs",
            "✅ CLEAN" if failure_count == 0 else "❌ DIRTY",
            success_count,
            failure_count,
            duration,
        )

        # Record the construction phase outcome
        self.tracer.record(
            agent="ExecutionAgent",
            decision_type="plan_execution",
            rationale=f"Executed blueprint for: {detailed_plan.goal}",
            chosen_action="Sequential construction",
            context={
                "steps": len(results),
                "success": success_count,
                "fail": failure_count,
                "aborted": aborted_at_step is not None,
            },
            confidence=1.0 if failure_count == 0 else 0.4,
        )

        return ExecutionResults(
            steps=results,
            success_count=success_count,
            failure_count=failure_count,
            total_duration_sec=duration,
            metadata=metadata,
        )

    # ID: c3d4e5f6-789a-bcde-f012-3456789abcde
    async def _execute_step(
        self,
        step: DetailedPlanStep,
        step_number: int,
    ) -> ActionResult:
        """
        Invokes the ActionExecutor for a single atomic action.
        """
        try:
            # All mutations flow through this Gateway (Mind/Body boundary)
            # 'write=True' is used here because the decision was validated by the Trial.
            result = await self.executor.execute(
                action_id=step.action,
                write=True,
                **step.params,
            )

            return result

        except Exception as e:
            logger.error("Execution Exception in step %d: %s", step_number, e)

            # Return a failed ActionResult to keep the pipeline stable
            return ActionResult(
                action_id=step.action,
                ok=False,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                duration_sec=0.0,
            )

    # ID: 55112e4c-696a-41a9-b32d-0a8cf16ff338
    def get_decision_trace(self) -> str:
        return self.tracer.format_trace()

    # ID: af34975e-a553-471e-a7b1-7b739d7d6eb4
    def save_decision_trace(self) -> None:
        self.tracer.save_trace()
