# src/will/phases/code_generation_phase.py

"""
Code Generation Phase - Intelligent Reflex Pipe.

For ``refactor_modularity`` workflows the LLM no longer writes split code.
Instead it produces a ``SplitPlan`` (boundary decisions only) and
``ModularitySplitter`` performs all file work deterministically.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from body.atomic.modularity_splitter import ModularitySplitter, SplitResult
from body.atomic.split_plan import SplitPlan, SplitPlanError
from body.services.file_service import FileService
from shared.ai.prompt_model import PromptModel
from shared.infrastructure.context.limb_workspace import LimbWorkspace
from shared.infrastructure.context.service import ContextService
from shared.logger import getLogger
from shared.models.workflow_models import DetailedPlan, DetailedPlanStep, PhaseResult
from will.orchestration.decision_tracer import DecisionTracer
from will.test_generation.sandbox import PytestSandboxRunner

from .code_generation.artifact_saver import ArtifactSaver
from .code_generation.code_sensor import CodeSensor
from .code_generation.file_path_extractor import FilePathExtractor
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

        # ----- Deterministic split path for modularity refactors ----------
        if context.workflow_type == "refactor_modularity":
            return await self._execute_deterministic_split(context, start_time)

        logger.info("Starting Intelligent Reflex Loop for %d steps...", len(plan))

        # 1. Create the Shadow Truth (Limb Workspace)
        workspace = LimbWorkspace(self.context.git_service.repo_path)

        # 2. Split-Brain Resolution - Localize ContextService to the Workspace:
        global_ctx_svc = self.context.context_service

        # Fork the senses
        localized_context_service = ContextService(
            qdrant_client=global_ctx_svc._qdrant_client,
            cognitive_service=global_ctx_svc._cognitive_service,
            config=global_ctx_svc.config,
            project_root=str(self.context.git_service.repo_path),
            session_factory=self.context.registry.session,
            workspace=workspace,
        )

        logger.info(
            "✅ ContextService localized to LimbWorkspace (Shadow Truth enabled)"
        )

        # Lazy imports reduce cross-layer coupling
        from will.agents.coder_agent import CoderAgent
        from will.orchestration.prompt_pipeline import PromptPipeline

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

        return PhaseResult(
            name="code_generation",
            ok=success_rate >= 0.8,
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

                current_code = code

                for attempt in range(metadata["max_repair_attempts"]):
                    logger.info(
                        "Repair attempt %d/%d...",
                        attempt + 1,
                        metadata["max_repair_attempts"],
                    )
                    repaired_code = await coder.generate_or_repair(
                        task, goal, pain_signal=pain_signal, previous_code=current_code
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

    # ------------------------------------------------------------------
    # Deterministic split path (refactor_modularity)
    # ------------------------------------------------------------------

    _SPLIT_PLAN_SYSTEM_PROMPT = (
        "You are a modularization planner.  You receive a Python source file "
        "and its already-identified responsibility clusters.  Your ONLY job is "
        "to produce a SplitPlan as JSON.  Do not write any code.  Do not "
        "explain anything outside the JSON."
    )

    _SPLIT_PLAN_USER_TEMPLATE = """\
Responsibility clusters already identified:
{clusters}

File: {source_file}

Source (for reference — do NOT rewrite it):
```python
{source_code}
```

Produce JSON matching exactly this schema:
{{
  "source_file": "...",
  "new_package_name": "...",
  "modules": [
    {{
      "module_name": "snake_case_name",
      "symbols": ["SymbolName", "function_name"],
      "rationale": "one sentence"
    }}
  ]
}}

Rules:
- Every top-level class and function must appear in exactly one module
- module_name must be a valid Python identifier
- At least 2 modules required
- new_package_name should match the original filename without .py
"""

    # ID: c3a1b2d4-5e6f-7a8b-9c0d-1e2f3a4b5c6d
    async def _execute_deterministic_split(
        self, context: WorkflowContext, start_time: float
    ) -> PhaseResult:
        """LLM decides boundaries only; AST machinery does all file work."""
        plan = context.results.get("planning", {}).get("execution_plan", [])
        repo_root = self.context.git_service.repo_path

        logger.info(
            "Deterministic split path: %d plan step(s) for refactor_modularity",
            len(plan),
        )

        split_results: list[dict[str, Any]] = []

        for task in plan:
            file_path_str = getattr(getattr(task, "params", None), "file_path", None)
            if not file_path_str:
                continue

            source_path = repo_root / file_path_str
            if not source_path.exists():
                logger.warning("Source file not found: %s", source_path)
                continue

            source_code = source_path.read_text(encoding="utf-8")

            # --- Gather responsibility clusters from earlier phases -------
            clusters_raw = context.results.get("planning", {}).get("clusters", [])
            clusters_text = (
                json.dumps(clusters_raw, indent=2)
                if clusters_raw
                else "No pre-identified clusters available.  Infer from the source."
            )

            # --- Ask the LLM for boundary decisions only ------------------
            split_plan_result = await self._request_split_plan(
                source_file=file_path_str,
                source_code=source_code,
                clusters_text=clusters_text,
            )

            if split_plan_result is None:
                split_results.append(
                    {
                        "file": file_path_str,
                        "ok": False,
                        "error": "LLM failed to produce a valid SplitPlan",
                    }
                )
                continue

            # --- Deterministic split via AST ------------------------------
            splitter = ModularitySplitter()
            try:
                result: SplitResult = splitter.split(source_path, split_plan_result)
            except SplitPlanError as exc:
                logger.error("Split failed for %s: %s", file_path_str, exc)
                split_results.append(
                    {
                        "file": file_path_str,
                        "ok": False,
                        "error": str(exc),
                    }
                )
                continue

            split_results.append(
                {
                    "file": file_path_str,
                    "ok": True,
                    "split_result": result,
                    "plan": split_plan_result,
                }
            )

        ok = any(r.get("ok") for r in split_results)

        return PhaseResult(
            name="code_generation",
            ok=ok,
            data={
                "deterministic_split": True,
                "split_results": split_results,
            },
            duration_sec=time.perf_counter() - start_time,
        )

    # ID: f1e2d3c4-b5a6-4789-0abc-def012345678
    async def _request_split_plan(
        self,
        source_file: str,
        source_code: str,
        clusters_text: str,
    ) -> SplitPlan | None:
        """Ask the LLM for a SplitPlan JSON; parse and validate it.

        Returns None if the LLM response is unparseable or invalid.
        """
        user_prompt = self._SPLIT_PLAN_USER_TEMPLATE.format(
            clusters=clusters_text,
            source_file=source_file,
            source_code=source_code,
        )

        try:
            client = await self.context.cognitive_service.aget_client_for_role("Coder")

            model = PromptModel.load("code_generation_task_step_prompt")
            raw_response = await model.invoke(
                context={
                    "task_step": (self._SPLIT_PLAN_SYSTEM_PROMPT + "\n\n" + user_prompt)
                },
                client=client,
                user_id="deterministic_split_planner",
            )

            # Extract JSON from response (may be wrapped in ```json fences)
            json_str = self._extract_json(raw_response)
            plan = SplitPlan.from_llm_json(json_str)
            logger.info(
                "SplitPlan validated: %d modules for %s",
                len(plan.modules),
                source_file,
            )
            return plan

        except SplitPlanError as exc:
            logger.error("SplitPlan validation failed: %s", exc)
            return None
        except Exception as exc:
            logger.error("SplitPlan request failed: %s", exc)
            return None

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code fences to expose raw JSON."""
        stripped = text.strip()
        if stripped.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = stripped.index("\n")
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        return stripped.strip()
