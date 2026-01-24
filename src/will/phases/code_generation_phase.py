# src/will/phases/code_generation_phase.py

"""
Code Generation Phase - Intelligent Reflex Pipe.

UPGRADED (V2.3): Multi-Modal Sensation.
The limb distinguishes between:
- Structural Integrity (logic / syntax)
- Functional Correctness (tests)

This prevents false-negative "pain" signals that cause unnecessary rework.

ENHANCED (V2.4): Artifact Documentation
- Saves all generated code to work/ directory for review
- Creates detailed reports even in dry-run mode
- Uses FileHandler for constitutional governance compliance

Constitutional Alignment:
- Pillar I (Octopus): Context-aware sensation.
- Pillar III (Governance): Logic-first validation.
- governance.artifact_mutation.traceable: All writes via FileHandler
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from features.test_generation_v2.sandbox import PytestSandboxRunner
from shared.infrastructure.context.limb_workspace import LimbWorkspace
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models.execution_models import DetailedPlan, DetailedPlanStep
from shared.models.workflow_models import PhaseResult
from will.orchestration.decision_tracer import DecisionTracer

from .code_generation.artifact_saver import ArtifactSaver
from .code_generation.code_sensor import CodeSensor
from .code_generation.file_path_extractor import FilePathExtractor
from .code_generation.work_directory_manager import WorkDirectoryManager


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: f6ad5be7-dde6-467b-8edf-767dfe62bfa2
class CodeGenerationPhase:
    """
    Code Generation Phase Component.

    ENHANCED: Now saves all generated code artifacts to work/ directory
    for review, debugging, and audit purposes.
    """

    def __init__(self, core_context: CoreContext) -> None:
        self.context = core_context
        self.tracer = DecisionTracer(agent_name="CodeGenerationPhase")

        # Initialize components
        self.file_handler = FileHandler(str(core_context.git_service.repo_path))
        self.execution_sensor = PytestSandboxRunner(
            core_context.file_handler,
            repo_root=str(core_context.git_service.repo_path),
        )

        self.work_dir_manager = WorkDirectoryManager(self.file_handler)
        self.artifact_saver = ArtifactSaver(self.file_handler)
        self.code_sensor = CodeSensor(self.execution_sensor)
        self.path_extractor = FilePathExtractor()

    # ID: e884ad19-65fd-451c-84aa-004494b56a6b
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

        # Lazy imports reduce cross-layer coupling
        from will.agents.coder_agent import CoderAgent
        from will.orchestration.prompt_pipeline import PromptPipeline

        coder = CoderAgent(
            cognitive_service=self.context.cognitive_service,
            prompt_pipeline=PromptPipeline(self.context.git_service.repo_path),
            auditor_context=self.context.auditor_context,
            repo_root=self.context.git_service.repo_path,
            workspace=workspace,
        )

        # Create work directory for artifacts
        work_dir_rel = self.work_dir_manager.create_session_directory(context.goal)

        # Process each task
        detailed_steps = await self._process_tasks(plan, coder, workspace, context.goal)

        if not detailed_steps:
            return PhaseResult(
                name="code_generation",
                ok=False,
                error="No executable (mutating) steps were processed.",
                duration_sec=time.perf_counter() - start_time,
            )

        # Save all generated artifacts
        self.artifact_saver.save_generation_artifacts(
            detailed_steps, work_dir_rel, context.goal
        )

        # Calculate success rate
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
                "artifacts_dir": work_dir_rel,
            },
            duration_sec=time.perf_counter() - start_time,
        )

    async def _process_tasks(
        self, plan: list, coder, workspace, goal: str
    ) -> list[DetailedPlanStep]:
        """Process all tasks in the plan through reflex loop."""
        detailed_steps = []
        max_twitches = 3

        for i, task in enumerate(plan, 1):
            # Skip read-only tasks in code generation phase
            if self._is_read_only_task(task):
                logger.info(
                    "Step %d/%d: Skipping read-only task in Code Generation phase.",
                    i,
                    len(plan),
                )
                continue

            task_step = getattr(task, "step", "") or ""
            logger.info("Step %d/%d: %s", i, len(plan), task_step)

            # Process task through reflex loop
            step = await self._reflex_loop(
                task, coder, workspace, goal, i, max_twitches
            )
            detailed_steps.append(step)

        return detailed_steps

    @staticmethod
    def _is_read_only_task(task: object) -> bool:
        """Check if task is read-only (no code generation needed)."""
        task_action = getattr(task, "action", None)
        task_step = getattr(task, "step", "") or ""

        return task_action in ("file.read", "inspect", "analyze") or "Read" in task_step

    async def _reflex_loop(
        self, task, coder, workspace, goal: str, step_index: int, max_twitches: int
    ) -> DetailedPlanStep:
        """Execute reflex loop with sensation and self-correction."""
        file_path = self.path_extractor.extract(task, step_index)
        current_code: str | None = None
        pain_signal: str | None = None
        step_ok = False

        for twitch in range(max_twitches + 1):
            if twitch > 0:
                logger.info("Twitch %d: Self-correcting based on sensation...", twitch)

            # A) GENERATE / REPAIR
            current_code = await coder.generate_or_repair(
                task=task,
                goal=goal,
                pain_signal=pain_signal,
                previous_code=current_code,
            )

            # B) SENSE (Multi-modal)
            sensation_ok, pain_signal = await self.code_sensor.sense_artifact(
                file_path, current_code or ""
            )

            if sensation_ok:
                logger.info("Sensation: CLEAR.")
                workspace.update_crate({file_path: current_code or ""})
                step_ok = True
                break

            logger.warning("Sensation: PAIN. Error: %s", (pain_signal or "")[:200])

        # Build step result
        step = DetailedPlanStep.from_execution_task(task, code=current_code)
        if not step_ok:
            step.metadata["generation_failed"] = True
            step.metadata["error"] = pain_signal
            logger.error("Twitch limit reached. Step failed.")

        return step
