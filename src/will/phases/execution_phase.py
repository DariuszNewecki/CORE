# src/will/phases/execution_phase.py
# ID: will.phases.execution_phase

"""
Execution Phase - Applies generated code to filesystem

Takes DetailedPlan from CODE_GENERATION phase and executes it
using ExecutionAgent, respecting write mode and constitutional boundaries.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.executor import ActionExecutor
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.agents.execution_agent import ExecutionAgent


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 1f2e3d4c-5b6a-7890-cdef-1234567890ab
class ExecutionPhase:
    """
    Execution phase - applies generated code to filesystem.

    Constitutional guarantees:
    - Respects write=False (dry-run mode)
    - Uses ActionExecutor for all filesystem operations
    - Captures files_written for downstream phases
    - Returns success only if all critical steps succeed
    """

    def __init__(self, context: CoreContext):
        self.context = context

    # ID: 2a3b4c5d-6e7f-8901-abcd-ef1234567890
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        """Execute the detailed plan from CODE_GENERATION phase."""
        start = time.time()

        # Extract detailed_plan from previous phase
        code_gen_data = ctx.results.get("code_generation", {})
        detailed_plan = code_gen_data.get("detailed_plan")

        if not detailed_plan:
            return PhaseResult(
                name="execution",
                ok=False,
                error="No detailed_plan found from code_generation phase",
                duration_sec=time.time() - start,
            )

        # Respect write mode from workflow context
        if not ctx.write:
            logger.info("Dry-run mode: Simulating execution without writing files")
            return PhaseResult(
                name="execution",
                ok=True,
                data={
                    "dry_run": True,
                    "steps_planned": len(detailed_plan.steps),
                    "files_written": [],
                },
                duration_sec=time.time() - start,
            )

        # Execute the plan using ExecutionAgent
        logger.info("🚀 Executing %d steps...", len(detailed_plan.steps))

        executor = ActionExecutor(self.context)
        agent = ExecutionAgent(executor=executor, write=ctx.write)

        try:
            exec_results = await agent.execute_plan(detailed_plan)

            duration = time.time() - start

            # ExecutionResults now has simple structure: success, files_written, errors, warnings
            return PhaseResult(
                name="execution",
                ok=exec_results.success,
                data={
                    "files_written": exec_results.files_written,
                    "errors_count": len(exec_results.errors),
                    "warnings_count": len(exec_results.warnings),
                },
                error=(
                    ""
                    if exec_results.success
                    else f"{len(exec_results.errors)} errors occurred"
                ),
                duration_sec=duration,
            )

        except Exception as e:
            logger.error("Execution phase crashed: %s", e, exc_info=True)
            return PhaseResult(
                name="execution",
                ok=False,
                error=f"Execution crashed: {e}",
                duration_sec=time.time() - start,
            )
