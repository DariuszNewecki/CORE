# src/will/phases/code_generation_phase.py
# ID: f6ad5be7-dde6-467b-8edf-767dfe62bfa2

"""
Code Generation Phase - Intelligent Reflex Pipe.

UPGRADED (V2.3): Multi-Modal Sensation.
ENHANCED (V2.4): Artifact Documentation.
HEALED (V2.6): Wired via Shared Protocols to support decoupled Execution.
CONTEXT_PACKAGE_FIX (V2.7): Added ContextService to CoderAgent initialization.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.services.file_service import FileService
from features.test_generation.sandbox import PytestSandboxRunner
from shared.infrastructure.context.limb_workspace import LimbWorkspace
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
    from will.agents.coder_agent import CoderAgent
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: f6ad5be7-dde6-467b-8edf-767dfe62bfa2
class CodeGenerationPhase:
    """
    Code Generation Phase Component.

    Orchestrates the Intelligent Reflex Loop. Now injects the
    ActionExecutor via CoreContext into the agent layer.
    """

    def __init__(self, core_context: CoreContext) -> None:
        """
        Initialize code generation phase.
        """
        self.context = core_context
        self.tracer = DecisionTracer(
            path_resolver=core_context.path_resolver,
            agent_name="CodeGenerationPhase",
        )

        self.file_service = FileService(core_context.git_service.repo_path)

        self.execution_sensor = PytestSandboxRunner(
            file_handler=core_context.file_handler,
            repo_root=str(core_context.git_service.repo_path),
        )

        self.work_dir_manager = WorkDirectoryManager(self.file_service)
        self.artifact_saver = ArtifactSaver(self.file_service)
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

        # CONTEXT_PACKAGE_FIX: Get ContextService from CoreContext
        context_service = None
        try:
            context_service = self.context.context_service
            logger.info("âœ… ContextService available for enriched code generation")
        except Exception as e:
            logger.warning("ContextService not available, using basic mode: %s", e)

        # HEALED WIRING: We pass self.context.action_executor (the Gateway)
        # into the CoderAgent so it no longer needs Late Imports.
        # CONTEXT_PACKAGE_FIX: Added context_service parameter
        coder = CoderAgent(
            cognitive_service=self.context.cognitive_service,
            executor=self.context.action_executor,  # <--- THE CONTRACT IS SIGNED
            prompt_pipeline=PromptPipeline(self.context.git_service.repo_path),
            auditor_context=self.context.auditor_context,
            repo_root=self.context.git_service.repo_path,
            context_service=context_service,  # <--- CONTEXT_PACKAGE_FIX: Added this line
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
                "detailed_plan": DetailedPlan(
                    goal=context.goal,
                    steps=detailed_steps,
                    initial_analysis="",
                ).dict(),
                "success_rate": success_rate,
                "total_steps": len(detailed_steps),
                "successful_steps": success_count,
                "work_directory": work_dir_rel,
            },
            duration_sec=time.perf_counter() - start_time,
        )

    async def _process_tasks(
        self,
        plan: list,
        coder: CoderAgent,
        workspace: LimbWorkspace,
        goal: str,
    ) -> list[DetailedPlanStep]:
        """
        Process execution plan tasks using the reflexive agent.

        Args:
            plan: Execution plan from planning phase
            coder: CoderAgent instance
            workspace: LimbWorkspace for simulated execution
            goal: Overall refactoring goal

        Returns:
            List of detailed plan steps with code and metadata
        """
        detailed_steps = []

        for task in plan:
            # Skip tasks without params
            if not hasattr(task, "params"):
                continue

            # Extract file_path
            file_path = self.path_extractor.extract(task)
            if not file_path:
                logger.warning("Skipping task with no file_path: %s", task.step)
                continue

            logger.info("Processing task: %s", task.step)

            # Generate or repair code (Reflex #1)
            code = await coder.generate_or_repair(task, goal)

            # Sense code (Reflex #2)
            sensation = await self.code_sensor.sense(code, file_path, workspace)

            # Add max_repair_attempts to metadata
            metadata = {
                "sensation": sensation,
                "max_repair_attempts": 3,
            }

            # If sensation shows pain, attempt repair
            if sensation.get("validation_passed") is False:
                pain_signal = sensation.get("error_message", "Unknown error")
                logger.warning("Pain detected: %s", pain_signal)

                for attempt in range(metadata["max_repair_attempts"]):
                    logger.info(
                        "Repair attempt %d/%d...",
                        attempt + 1,
                        metadata["max_repair_attempts"],
                    )
                    repaired_code = await coder.generate_or_repair(
                        task, goal, pain_signal=pain_signal, previous_code=code
                    )

                    # Re-sense
                    sensation = await self.code_sensor.sense(
                        repaired_code, file_path, workspace
                    )

                    if sensation.get("validation_passed"):
                        code = repaired_code
                        metadata["repair_succeeded"] = True
                        metadata["repair_attempts"] = attempt + 1
                        break

                    pain_signal = sensation.get("error_message", "Unknown error")

                if not sensation.get("validation_passed"):
                    metadata["repair_failed"] = True
                    metadata["generation_failed"] = True

            # Create detailed step
            step = DetailedPlanStep(
                step=task.step,
                action=task.action,
                params=(
                    task.params.dict() if hasattr(task.params, "dict") else task.params
                ),
                code=code,
                metadata=metadata,
            )

            detailed_steps.append(step)

        return detailed_steps
