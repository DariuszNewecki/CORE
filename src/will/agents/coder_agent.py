# src/will/agents/coder_agent.py

"""
CoderAgent - Reflexive code generation specialist.

Implements the "Reflexive Neuron" pattern. Accepts pain signals from runtime
failures and uses LimbWorkspace sensation to understand the impact of changes.
Distinguishes between initial generation and reflexive repair.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask
from will.agents.code_generation import (
    CodeGenerator,
    CorrectionEngine,
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

    Orchestrates code generation and repair by combining LLM reasoning with
    sensory feedback from the workspace and canary signals.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: Any,
        auditor_context: AuditorContext,
        context_service: ContextService | None = None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context
        self.context_service = context_service
        self.workspace = workspace
        self.tracer = DecisionTracer(agent_name="ReflexiveCoder")

        self.repo_root = settings.REPO_PATH
        intent_guard = IntentGuard(self.repo_root)
        self.pattern_validator = PatternValidator(intent_guard)
        self.correction_engine = CorrectionEngine(
            cognitive_service, auditor_context, self.tracer
        )

        self.code_generator = CodeGenerator(
            cognitive_service=cognitive_service,
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
        Reflex entry point.

        Chooses between initial generation and reflexive repair based on
        whether a pain signal is present.
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
        """Reflexive repair using sensory pain to adjust the code logic."""
        logger.warning("Reflex: Sensory pain detected. Initiating repair.")

        self.tracer.record(
            agent="ReflexiveCoder",
            decision_type="reflexive_repair",
            rationale="Previous attempt triggered a sensation failure (Canary/Traceback)",
            chosen_action="LLM-based logic correction",
            context={"pain": pain_signal[:200], "step": task.step},
            confidence=0.5,
        )

        repair_prompt = f"""
            SENSORY FEEDBACK (PAIN SIGNAL)
            The code you generated previously failed in the execution sandbox.
            ERROR:
            {pain_signal}
            MISSION RECAP
            Goal: {goal}
            Task: {task.step}
            PREVIOUS CODE
            {previous_code or "# Missing previous code"}
            INSTRUCTION
            Analyze the error above. It is a real signal from the environment.
            Fix the logic to resolve this error.
            If it is an ImportError, verify the new module structure.
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
        return fixed_code

    # ID: validate_neuron_output
    # ID: 1801d0a5-ded5-4f76-b85b-f6b2ce547b11
    async def validate_output(self, code: str, file_path: str) -> dict[str, Any]:
        """Perform structural and constitutional checks on generated output."""
        return await validate_code_async(
            code,
            file_path,
            self.auditor_context,
        )
