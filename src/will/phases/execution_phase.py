# src/will/phases/execution_phase.py

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

        # Deterministic split path: ModularitySplitter produced SplitResults
        # that still need to be written to disk.
        if code_gen_data.get("deterministic_split"):
            split_results = code_gen_data.get("split_results", [])
            return await self._execute_deterministic_split(
                split_results, ctx.write, start
            )

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

    # ID: 7c8d9e0f-1a2b-3c4d-5e6f-7a8b9c0d1e2f
    async def _execute_deterministic_split(
        self,
        split_results: list[dict],
        write: bool,
        start: float,
    ) -> PhaseResult:
        """Write SplitResult files to disk and remove the original source."""
        file_handler = self.context.file_handler
        repo_root = self.context.git_service.repo_path
        files_written: list[str] = []
        files_deleted: list[str] = []

        for entry in split_results:
            if not entry.get("ok"):
                continue

            split_result = entry.get("split_result")
            if split_result is None:
                continue

            if not write:
                for file_path, _content in split_result.files:
                    logger.info("Dry-run: would write %s", file_path)
                if split_result.original_path.exists():
                    logger.info("Dry-run: would delete %s", split_result.original_path)
                continue

            # Write each new module file
            for file_path, content in split_result.files:
                rel_path = str(file_path.relative_to(repo_root))
                file_handler.write_runtime_text(rel_path, content)
                files_written.append(rel_path)
                logger.info("Wrote split module: %s", rel_path)

            # Delete the original monolith file
            if split_result.original_path.exists():
                rel_original = str(split_result.original_path.relative_to(repo_root))
                split_result.original_path.unlink()
                files_deleted.append(rel_original)
                logger.info("Deleted original: %s", rel_original)

        if not write:
            return PhaseResult(
                name="execution",
                ok=True,
                data={"dry_run": True, "files_written": []},
                duration_sec=time.time() - start,
            )

        return PhaseResult(
            name="execution",
            ok=bool(files_written),
            data={
                "deterministic_split": True,
                "files_written": files_written,
                "files_deleted": files_deleted,
            },
            duration_sec=time.time() - start,
        )
