# src/will/phases/code_generation_phase.py

"""
Code Generation Phase - Intelligent Reflex Pipe.

UPGRADED (V2.3): Multi-Modal Sensation.
The limb distinguishes between:
- Structural Integrity (logic / syntax)
- Functional Correctness (tests)

This prevents false-negative “pain” signals that cause unnecessary rework.

Constitutional Alignment:
- Pillar I (Octopus): Context-aware sensation.
- Pillar III (Governance): Logic-first validation.
"""

from __future__ import annotations

import ast
import time
from typing import TYPE_CHECKING

from features.test_generation_v2.sandbox import PytestSandboxRunner
from shared.infrastructure.context.limb_workspace import LimbWorkspace
from shared.logger import getLogger
from shared.models.workflow_models import DetailedPlan, DetailedPlanStep, PhaseResult
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: code_generation_reflex_pipe
# ID: 3c4d5e6f-7g8h-9i0j-1k2l-3m4n5o6p7q8r
# ID: b481078f-65e9-4fea-8870-373fa2a52850
class CodeGenerationPhase:
    """Orchestrates the intelligent reflexive generation loop."""

    def __init__(self, core_context: CoreContext) -> None:
        self.context = core_context
        self.tracer = DecisionTracer(agent_name="IntelligentReflexPipe")
        self.execution_sensor = PytestSandboxRunner(
            core_context.file_handler,
            repo_root=str(core_context.git_service.repo_path),
        )

    # ID: execute_intelligent_loop
    # ID: 278cf35e-d02b-417f-a7c8-680420ae6562
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute the reflexive loop with multi-modal sensation."""
        start_time = time.perf_counter()

        plan = context.results.get("planning", {}).get("execution_plan", [])
        if not plan:
            return PhaseResult(
                name="code_generation", ok=False, error="No plan provided"
            )

        logger.info("Starting Intelligent Reflex Loop for %d steps...", len(plan))

        workspace = LimbWorkspace(self.context.git_service.repo_path)

        # Lazy imports reduce cross-layer coupling and avoid cycles during orchestration.
        from will.agents.coder_agent import CoderAgent
        from will.orchestration.prompt_pipeline import PromptPipeline

        coder = CoderAgent(
            cognitive_service=self.context.cognitive_service,
            prompt_pipeline=PromptPipeline(self.context.git_service.repo_path),
            auditor_context=self.context.auditor_context,
            workspace=workspace,
        )

        detailed_steps: list[DetailedPlanStep] = []
        max_twitches = 3

        for i, task in enumerate(plan, 1):
            # Skip non-mutating tasks in the Code Generation phase.
            # Reading is "sensation" handled by the workspace, not a generation step.
            task_action = getattr(task, "action", None)
            task_step = getattr(task, "step", "") or ""
            if (
                task_action in ("file.read", "inspect", "analyze")
                or "Read" in task_step
            ):
                logger.info(
                    "Step %d/%d: Skipping read-only task in Code Generation phase.",
                    i,
                    len(plan),
                )
                continue

            logger.info("Step %d/%d: %s", i, len(plan), task_step)

            current_code: str | None = None
            pain_signal: str | None = None
            step_ok = False

            for twitch in range(max_twitches + 1):
                if twitch > 0:
                    logger.info(
                        "Twitch %d: Self-correcting based on sensation...", twitch
                    )

                # A) GENERATE / REPAIR
                current_code = await coder.generate_or_repair(
                    task=task,
                    goal=context.goal,
                    pain_signal=pain_signal,
                    previous_code=current_code,
                )

                # B) SENSE (Multi-modal)
                file_path = self._extract_file_path(task, i)
                sensation_ok, pain_signal = await self._sense_artifact(
                    file_path, current_code or ""
                )

                if sensation_ok:
                    logger.info("Sensation: CLEAR.")
                    workspace.update_crate({file_path: current_code or ""})
                    step_ok = True
                    break

                logger.warning(
                    "Sensation: PAIN. Error: %s",
                    (pain_signal or "")[:200],
                )

            step = DetailedPlanStep.from_execution_task(task, code=current_code)
            if not step_ok:
                step.metadata["generation_failed"] = True
                step.metadata["error"] = pain_signal
                logger.error("Twitch limit reached. Step failed.")

            detailed_steps.append(step)

        if not detailed_steps:
            return PhaseResult(
                name="code_generation",
                ok=False,
                error="No executable (mutating) steps were processed.",
                duration_sec=time.perf_counter() - start_time,
            )

        success_count = sum(
            1 for s in detailed_steps if not s.metadata.get("generation_failed")
        )
        success_rate = success_count / len(detailed_steps)

        return PhaseResult(
            name="code_generation",
            ok=success_rate >= 0.8,
            data={
                "detailed_plan": DetailedPlan(goal=context.goal, steps=detailed_steps),
                "success_rate": success_rate,
                "workspace": workspace.get_crate_content(),
            },
            duration_sec=time.perf_counter() - start_time,
        )

    def _extract_file_path(self, task: object, step_index: int) -> str:
        """
        Best-effort extraction of a target file path from a task.

        This phase often operates on task objects coming from planning that may
        be typed loosely; keep this defensive and deterministic.
        """
        params = getattr(task, "params", None)
        file_path = None

        if params is not None:
            file_path = getattr(params, "file_path", None)
            if not file_path and isinstance(params, dict):
                file_path = params.get("file_path")

        if file_path and isinstance(file_path, str):
            return file_path

        return f"work/temp_step_{step_index}.py"

    # ID: multi_modal_sensation_logic
    async def _sense_artifact(
        self, file_path: str, code: str
    ) -> tuple[bool, str | None]:
        """
        Multi-modal sensation logic.

        - Structural sensation (universal): Python syntax must parse.
        - Functional sensation (tests): If the artifact looks like a test, run pytest sandbox.
        """
        if not code:
            return False, "No code generated."

        # 1) STRUCTURAL SENSATION (universal)
        if file_path.endswith(".py"):
            try:
                ast.parse(code)
            except SyntaxError as e:
                return False, f"Syntax Error: {e}"

        # 2) MODALITY SELECTION
        is_test = (
            ("test_" in file_path)
            or ("/tests/" in file_path)
            or ("\\tests\\" in file_path)
        )

        if is_test:
            logger.debug("Modality: Functional (Pytest) for %s", file_path)
            result = await self.execution_sensor.run(code, "reflex_check")
            if getattr(result, "passed", False):
                return True, None
            return False, getattr(result, "error", "Pytest failed.")
        else:
            logger.debug("Modality: Structural (AST) for %s", file_path)
            return True, None
