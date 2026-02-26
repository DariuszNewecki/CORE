# src/will/agents/execution_agent.py
# ID: 4b9a28f4-6c4d-4a5e-8f7c-9d0e1b2a3c4d

"""
The ExecutionAgent (Contractor): Executes validated code blueprints.

CONSTITUTIONAL FIX: Respects the 'write' flag from the orchestrator instead
of hardcoding write=True. Ensures dry-runs remain non-destructive.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
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

    Skips steps that failed code generation and enforces
    constitutional write-permission boundaries.
    """

    def __init__(self, executor: ActionExecutor, write: bool = False):
        """
        Initialize the ExecutionAgent.

        Args:
            executor: The ActionExecutor (The Body's Gateway).
            write: Whether to apply changes (True) or simulate (False).
        """
        self.executor = executor
        self.write = write
        self.tracer = DecisionTracer()

        logger.info(
            "ExecutionAgent initialized (Contractor Mode: write=%s)", self.write
        )

    # ID: b2c3d4e5-f678-90ab-cdef-0123456789ab
    async def execute_plan(
        self,
        detailed_plan: DetailedPlan,
    ) -> ExecutionResults:
        """
        Execute a DetailedPlan step-by-step.
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

            # Check if Step was marked as failed during Engineering phase
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

                if step.is_critical:
                    aborted_at_step = i
                    logger.error("⛔ Critical step failed during generation. Aborting.")
                    break
                continue

            # Execution via Constitutional Gateway
            result = await self._execute_step(step, step_number=i)
            results.append(result)

            if result.ok:
                success_count += 1
                logger.info("    → ✅ Step outcome: Success")
            else:
                failure_count += 1
                error = result.data.get("error", "Unknown error")
                logger.error("    → ❌ Step failed: %s", error)

                # CONSTITUTIONAL SAFETY: Abort on critical failure
                if step.is_critical:
                    aborted_at_step = i
                    logger.error("⛔ Critical step failed. Aborting construction.")
                    break

        duration = time.time() - start_time
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

        self.tracer.record(
            agent="ExecutionAgent",
            decision_type="plan_execution",
            rationale=f"Executed blueprint for: {detailed_plan.goal}",
            chosen_action="Sequential construction",
            context={
                "steps": len(results),
                "success": success_count,
                "fail": failure_count,
                "write_mode": self.write,
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
    @atomic_action(
        action_id="will.execution._execute_step",
        intent="Atomic action for _execute_step",
        impact=ActionImpact.WRITE_CODE,
        policies=["atomic_actions"],
    )
    async def _execute_step(
        self,
        step: DetailedPlanStep,
        step_number: int,
    ) -> ActionResult:
        """
        Invokes the ActionExecutor for a single atomic action.
        """
        try:
            # CONSTITUTIONAL FIX: Use self.write instead of hardcoded True
            result = await self.executor.execute(
                action_id=step.action,
                write=self.write,
                **step.params,
            )

            return result

        except Exception as e:
            logger.error("Execution Exception in step %d: %s", step_number, e)
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
