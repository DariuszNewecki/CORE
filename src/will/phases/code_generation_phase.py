# src/will/phases/code_generation_phase.py

"""
Code Generation Phase - Intelligent Reflex Pipe.

For ``refactor_modularity`` workflows the phase delegates to
``DeterministicSplitPlanner`` (``code_generation/split_planner.py``): the LLM
produces a ``SplitPlan`` (boundary decisions only) and ``ModularitySplitter``
performs all file work deterministically.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from shared.infrastructure.context.limb_workspace import LimbWorkspace
from shared.infrastructure.context.service import ContextService
from shared.logger import getLogger
from shared.models.workflow_models import DetailedPlan, DetailedPlanStep, PhaseResult
from will.orchestration.decision_tracer import DecisionTracer
from will.test_generation.sandbox import PytestSandboxRunner

from .code_generation.artifact_saver import ArtifactSaver
from .code_generation.code_sensor import CodeSensor
from .code_generation.file_path_extractor import FilePathExtractor
from .code_generation.split_planner import DeterministicSplitPlanner
from .code_generation.work_directory_manager import WorkDirectoryManager


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.agents.coder_agent import CoderAgent
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


def _serialize_detailed_plan(detailed_plan: DetailedPlan) -> dict:
    """Serialize DetailedPlan dataclass to JSON-safe dict."""
    return asdict(detailed_plan)


# ID: 1f1383bb-136d-4403-b359-73c7eae6b355
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

        self.file_service = core_context.file_service

        self.execution_sensor = PytestSandboxRunner(
            file_handler=self.file_service,
            repo_root=str(core_context.git_service.repo_path),
        )

        self.work_dir_manager = WorkDirectoryManager(self.file_service)
        self.artifact_saver = ArtifactSaver(self.file_service)
        self.code_sensor = CodeSensor(self.execution_sensor)
        self.path_extractor = FilePathExtractor()
        self.split_planner = DeterministicSplitPlanner(core_context)

    # ID: e884ad19-65fd-451c-84aa-004494b56a6b
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute the reflexive loop with multi-modal sensation."""
        start_time = time.perf_counter()

        plan = context.results.get("planning", {}).get("execution_plan", [])
        if not plan:
            return PhaseResult(
                name="code_generation", ok=False, error="No plan provided"
            )

        # ----- Deterministic split path for modularity refactors ----------
        if context.workflow_type == "refactor_modularity":
            return await self.split_planner.execute(context, start_time)

        logger.info("Starting Intelligent Reflex Loop for %d steps...", len(plan))

        # 1. Create the Shadow Truth (Limb Workspace)
        workspace = LimbWorkspace(self.context.git_service.repo_path)

        # 2. Split-Brain Resolution - Localize ContextService to the Workspace:
        global_ctx_svc = self.context.context_service

        # Fork the senses. Prefer the CoreContext's resolved services (set by
        # develop_from_goal warm-up) over the global service's private fields,
        # which may still be None before _ensure_brain_services() fires.
        localized_context_service = ContextService(
            qdrant_client=global_ctx_svc._qdrant_client or self.context.qdrant_service,
            cognitive_service=global_ctx_svc._cognitive_service
            or self.context.cognitive_service,
            config=global_ctx_svc.config,
            project_root=str(self.context.git_service.repo_path),
            session_factory=self.context.registry.session,
            workspace=workspace,
            brain_services_provider=global_ctx_svc._brain_services_provider,
        )

        logger.info(
            "✅ ContextService localized to LimbWorkspace (Shadow Truth enabled)"
        )

        # Lazy imports reduce cross-layer coupling
        from will.agents.coder_agent import CoderAgent
        from will.orchestration.prompt_pipeline import PromptPipeline

        if self.context.cognitive_service is None:
            return PhaseResult(
                name="code_generation",
                ok=False,
                error="cognitive_service not available",
            )
        if self.context.action_executor is None:
            return PhaseResult(
                name="code_generation", ok=False, error="action_executor not available"
            )
        if self.context.auditor_context is None:
            return PhaseResult(
                name="code_generation", ok=False, error="auditor_context not available"
            )

        # 3. Initialize Agent with the Localized Senses
        coder = CoderAgent(
            cognitive_service=self.context.cognitive_service,
            executor=self.context.action_executor,
            prompt_pipeline=PromptPipeline(self.context.git_service.repo_path),
            auditor_context=self.context.auditor_context,
            repo_root=self.context.git_service.repo_path,
            context_service=localized_context_service,  # <--- Passing the localized service
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
        detailed_plan = DetailedPlan(
            goal=context.goal,
            steps=detailed_steps,
        )
        detailed_plan_dict = _serialize_detailed_plan(detailed_plan)

        ok = success_rate >= 0.8
        return PhaseResult(
            name="code_generation",
            ok=ok,
            # The verdict must be STATED, not only carried in data: the
            # Worker's outcome record keeps a phase's name/ok/error, and an
            # exported run with "code_generation failed: None" says nothing
            # about why (#894 seeded live run, 3/5 steps on the pinned model).
            error=(
                ""
                if ok
                else (
                    f"code generation succeeded for {success_count}/"
                    f"{len(detailed_steps)} steps (success_rate "
                    f"{success_rate:.2f} < 0.80)"
                )
            ),
            data={
                "detailed_plan": detailed_plan,
                "detailed_plan_dict": detailed_plan_dict,
                "success_rate": success_rate,
                "total_steps": len(detailed_steps),
                "successful_steps": success_count,
                "work_directory": work_dir_rel,
            },
            duration_sec=time.perf_counter() - start_time,
        )

    @staticmethod
    # ID: 3a7c91d2-f4e5-4b8a-bc6d-7d0e1f2a3b4c
    def _extract_module_sources(pain_signal: str, repo_root: Path) -> str | None:
        """Read source for modules named in ImportError / TypeError tracebacks.

        Handles two patterns:
        - ``ImportError: cannot import name 'X' from 'pkg.module'``
        - ``File "/abs/path/to/src/module.py", line N``
        Returns a formatted string ready for prompt injection, or None.
        """
        sources: dict[str, str] = {}

        # Pattern 1: ImportError module path
        for m in re.finditer(
            r"from ['\"]([a-z_][a-z0-9_.]+)['\"]", pain_signal, re.IGNORECASE
        ):
            module_dotpath = m.group(1)
            rel = "src/" + module_dotpath.replace(".", "/") + ".py"
            candidate = repo_root / rel
            if candidate.is_file() and rel not in sources:
                sources[rel] = candidate.read_text(encoding="utf-8")

        # Pattern 2: traceback File lines inside src/
        for m in re.finditer(r'File "([^"]+/src/[^"]+\.py)"', pain_signal):
            abs_path = Path(m.group(1))
            if abs_path.is_file():
                try:
                    rel = str(abs_path.relative_to(repo_root))
                except ValueError:
                    rel = abs_path.name
                if rel not in sources:
                    sources[rel] = abs_path.read_text(encoding="utf-8")

        if not sources:
            return None

        parts = []
        for path, content in sources.items():
            parts.append(f"# Source: {path}\n```python\n{content}\n```")
        return "\n\n".join(parts)

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

        for i, task in enumerate(plan, 1):
            # Skip tasks without params
            if not hasattr(task, "params"):
                continue

            # Extract file_path (fixed — no nested loop anymore)
            file_path = self.path_extractor.extract(task, i)
            if not file_path:
                logger.warning(
                    "Skipping task with no file_path: %s",
                    getattr(task, "step", str(task)),
                )
                continue

            logger.info("Processing task: %s", getattr(task, "step", str(task)))

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
            if not sensation.get("passed", True):
                pain_signal = sensation.get("error", "Unknown error")
                logger.warning("Pain detected: %s", pain_signal)

                module_source_context = self._extract_module_sources(
                    pain_signal, workspace.repo_root
                )

                current_code = code

                for attempt in range(int(str(metadata["max_repair_attempts"]))):
                    logger.info(
                        "Repair attempt %d/%d...",
                        attempt + 1,
                        metadata["max_repair_attempts"],
                    )
                    repaired_code = await coder.generate_or_repair(
                        task,
                        goal,
                        pain_signal=pain_signal,
                        previous_code=current_code,
                        module_source_context=module_source_context,
                    )

                    # Re-sense
                    sensation = await self.code_sensor.sense(
                        repaired_code, file_path, workspace
                    )

                    if sensation.get("passed"):
                        code = repaired_code
                        metadata["repair_succeeded"] = True
                        metadata["repair_attempts"] = attempt + 1
                        break

                    # Advance both signal and base code for next attempt
                    pain_signal = sensation.get("error", "Unknown error")
                    current_code = repaired_code

                if not sensation.get("passed"):
                    metadata["repair_failed"] = True
                    metadata["generation_failed"] = True

            # Build step via from_execution_task so generated code is injected
            # into params. file.create and file.edit require params["code"] to
            # be present — the old manual construction was bypassing this.
            generated_code = code if not metadata.get("generation_failed") else None
            step = DetailedPlanStep.from_execution_task(task, code=generated_code)

            # Attach metadata
            step.metadata = metadata
            detailed_steps.append(step)

        return detailed_steps
