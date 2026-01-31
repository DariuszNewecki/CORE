# src/will/agents/coder_agent.py

"""
CoderAgent - Reflexive code generation specialist.

UPGRADED V2.4: Added Semantic Drift Detection.
Uses vector embeddings to sense if reflexive repairs are moving closer to
or further away from the mission goal. Prevents hallucination loops.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models import ExecutionTask
from shared.path_resolver import PathResolver
from will.agents.code_generation import (
    CodeGenerator,
    PatternValidator,
)
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.intent_guard import IntentGuard
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from shared.infrastructure.context.limb_workspace import LimbWorkspace
    from shared.infrastructure.context.service import ContextService
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: reflexive_coder_neuron
# ID: 917038e4-682f-4d7f-ad13-f5ab7835abc1
class CoderAgent:
    """
    The "Reflexive Neuron" of the Octopus limb.

    Orchestrates code generation and repair. Now senses "Semantic Drift"
    to identify when repairs are diverging from the mission intent.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: Any,
        auditor_context: AuditorContext,
        repo_root: Path,
        context_service: ContextService | None = None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context
        self.context_service = context_service
        self.workspace = workspace
        self.tracer = DecisionTracer(
            path_resolver=PathResolver(repo_root), agent_name="ReflexiveCoder"
        )

        self.repo_root = Path(repo_root).resolve()
        path_resolver = PathResolver.from_repo(
            repo_root=self.repo_root, intent_root=self.repo_root / ".intent"
        )
        intent_guard = IntentGuard(self.repo_root, path_resolver)
        self.pattern_validator = PatternValidator(intent_guard)

        self.code_generator = CodeGenerator(
            cognitive_service=cognitive_service,
            path_resolver=path_resolver,
            prompt_pipeline=prompt_pipeline,
            tracer=self.tracer,
            context_service=context_service,
        )

    # ID: reflexive_repair_loop
    # ID: 6a1fa37d-fa07-40be-bdcc-2741cd608c9c
    async def generate_or_repair(
        self,
        task: ExecutionTask,
        goal: str,
        pain_signal: str | None = None,
        previous_code: str | None = None,
    ) -> str:
        """
        Reflex entry point. Chooses between initial creation and sensory repair.
        """
        if pain_signal:
            return await self._repair_code(task, goal, pain_signal, previous_code)

        return await self._generate_initial(task, goal)

    async def _generate_initial(self, task: ExecutionTask, goal: str) -> str:
        """Standard A2 generation pipeline."""
        logger.info("Reflex: Generating initial logic for '%s'", task.step)

        pattern_id = self.pattern_validator.infer_pattern_id(task)
        requirements = self.pattern_validator.get_pattern_requirements(pattern_id)
        context_str = f"Mission Goal: {goal}"

        return await self.code_generator.generate_code(
            task, goal, context_str, pattern_id, requirements
        )

    # ID: repair_logic_from_sensation
    async def _repair_code(
        self,
        task: ExecutionTask,
        goal: str,
        pain_signal: str,
        previous_code: str | None,
    ) -> str:
        """Reflexive repair using sensory pain and Semantic Drift detection."""
        logger.warning("Reflex: Sensory pain detected. Initiating repair.")

        # 1. GENERATE REPAIR
        repair_prompt = f"""
            SENSORY FEEDBACK (PAIN SIGNAL)
            The code you generated previously failed in the execution sandbox.
            ERROR: {pain_signal}

            MISSION RECAP
            Goal: {goal}
            Task: {task.step}

            PREVIOUS CODE
            {previous_code or "# Missing previous code"}

            INSTRUCTION
            Analyze the error above. Fix the logic to resolve this error.
            Return ONLY the corrected Python code.
        """

        client = await self.cognitive_service.aget_client_for_role(
            "Coder", high_reasoning=True
        )
        response = await client.make_request_async(
            repair_prompt, user_id="reflex_repair"
        )

        from shared.utils.parsing import extract_python_code_from_response

        fixed_code = extract_python_code_from_response(response) or response

        # 2. SENSE SEMANTIC DRIFT (The "Hallucination Guard")
        # We check if the new code still relates to the Goal
        alignment_score = await self._calculate_alignment(fixed_code, goal)

        drift_status = "STABLE" if alignment_score > 0.4 else "DRIFTING"
        if drift_status == "DRIFTING":
            logger.error(
                "🚨 Semantic Drift Detected! Alignment Score: %.2f", alignment_score
            )

        # 3. RECORD IN TRACE
        self.tracer.record(
            agent="ReflexiveCoder",
            decision_type="reflexive_repair",
            rationale=f"Repaired based on pain signal. Semantic alignment: {drift_status}",
            chosen_action="LLM-based logic correction",
            context={
                "pain": pain_signal[:200],
                "step": task.step,
                "semantic_alignment": alignment_score,
                "status": drift_status,
            },
            confidence=alignment_score,
        )

        return fixed_code

    async def _calculate_alignment(self, code: str, goal: str) -> float:
        """
        Measures the semantic similarity between generated code and the goal.

        This is a pure 'Will' decision helper. It doesn't use standard math libraries
        to keep the Body layer lean, but uses the Vectorizer role.
        """
        try:
            # Get embeddings for both
            v_code = await self.cognitive_service.get_embedding_for_code(code[:2000])
            v_goal = await self.cognitive_service.get_embedding_for_code(goal)

            if not v_code or not v_goal:
                return 0.5  # Default neutral if embedding fails

            # Standard Dot Product (Vectors are already normalized by provider)
            return sum(a * b for a, b in zip(v_code, v_goal))
        except Exception as e:
            logger.debug("Alignment calculation failed: %s", e)
            return 0.5

    # ID: validate_neuron_output
    # ID: 1801d0a5-ded5-4f76-b85b-f6b2ce547b11
    async def validate_output(self, code: str, file_path: str) -> dict[str, Any]:
        """Perform structural and constitutional checks on generated output."""
        return await validate_code_async(
            file_path,
            code,
            auditor_context=self.auditor_context,
        )
