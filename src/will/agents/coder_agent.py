# src/will/agents/coder_agent.py
# ID: b51a4101-800d-4d61-a8af-78171bfd990c
# ID: 917038e4-682f-4d7f-ad13-f5ab7835abc1

"""
CoderAgent - Reflexive code generation specialist.

UPGRADED V2.4: Added Semantic Drift Detection.
CONSTITUTIONAL COMPLIANCE V2.5: Integrated RefusalResult handling.
HEALED V2.6: Wired via Shared Protocols to eliminate circular dependencies.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models import ExecutionTask
from shared.path_resolver import PathResolver
from shared.protocols.cognitive import CognitiveProtocol
from shared.protocols.executor import ActionExecutorProtocol
from will.agents.code_generation import (
    CodeGenerator,
    PatternValidator,
)
from will.agents.coder_agent_refusal_handler import handle_code_generation_result
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.intent_guard import IntentGuard
from will.orchestration.validation_pipeline import validate_code_async


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from shared.infrastructure.context.limb_workspace import LimbWorkspace
    from shared.infrastructure.context.service import ContextService

logger = getLogger(__name__)


# ID: 5b10aac1-26f0-4dcc-babb-e0845e17955e
class CoderAgent:
    """
    The "Reflexive Neuron" of the Octopus limb.

    Now utilizes CognitiveProtocol and ActionExecutorProtocol to ensure
    Mind-Body-Will separation while maintaining v2.5 refusal handling.
    """

    def __init__(
        self,
        cognitive_service: CognitiveProtocol,
        executor: ActionExecutorProtocol,  # ADDED: Healed wiring
        prompt_pipeline: Any,
        auditor_context: AuditorContext,
        repo_root: Path,
        context_service: ContextService | None = None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.cognitive_service = cognitive_service
        self.executor = executor  # HEALED: No late imports needed
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context
        self.context_service = context_service
        self.workspace = workspace

        self.repo_root = Path(repo_root).resolve()
        path_resolver = PathResolver.from_repo(
            repo_root=self.repo_root, intent_root=self.repo_root / ".intent"
        )

        self.tracer = DecisionTracer(
            path_resolver=path_resolver, agent_name="ReflexiveCoder"
        )

        intent_guard = IntentGuard(self.repo_root, path_resolver)
        self.pattern_validator = PatternValidator(intent_guard)

        self.code_generator = CodeGenerator(
            cognitive_service=self.cognitive_service,
            path_resolver=path_resolver,
            prompt_pipeline=prompt_pipeline,
            tracer=self.tracer,
            context_service=context_service,
        )

    # ID: 6a1fa37d-fa07-40be-bdcc-2741cd608c9c
    async def generate_or_repair(
        self,
        task: ExecutionTask,
        goal: str,
        pain_signal: str | None = None,
        previous_code: str | None = None,
    ) -> str:
        """Reflex entry point with v2.5 error handling."""
        if pain_signal:
            return await self._repair_code(task, goal, pain_signal, previous_code)

        return await self._generate_initial(task, goal)

    async def _generate_initial(self, task: ExecutionTask, goal: str) -> str:
        """A2 pipeline + v2.5 Refusal Handling."""
        logger.info("Reflex: Generating initial logic for '%s'", task.step)

        pattern_id = self.pattern_validator.infer_pattern_id(task)
        requirements = self.pattern_validator.get_pattern_requirements(pattern_id)
        context_str = f"Mission Goal: {goal}"

        # Call generator (using the injected protocol)
        code_or_refusal = await self.code_generator.generate_code(
            task, goal, context_str, pattern_id, requirements
        )

        # PRESERVED: v2.5 Handle refusal or get code
        code = await handle_code_generation_result(
            code_or_refusal,
            session_id=(
                self.tracer.session_id if hasattr(self.tracer, "session_id") else None
            ),
            user_id=None,
        )

        return code

    # ID: b5c1fb36-8266-4888-9840-9297ab7ffca3
    async def _repair_code(
        self,
        task: ExecutionTask,
        goal: str,
        pain_signal: str,
        previous_code: str | None,
    ) -> str:
        """Reflexive repair with v2.4 drift detection and v2.5 refusal logging."""
        logger.warning("Reflex: Sensory pain detected. Initiating repair.")

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
            Return ONLY the corrected Python code in ```python fences.
        """

        client = await self.cognitive_service.aget_client_for_role(
            "Coder", high_reasoning=True
        )
        response = await client.make_request_async(
            repair_prompt, user_id="reflex_repair"
        )

        from shared.utils.parsing import extract_python_code_from_response

        fixed_code = extract_python_code_from_response(response)

        # PRESERVED: v2.5 Refusal Case Recording
        if not fixed_code:
            logger.error("Failed to extract code from repair response")
            from shared.component_primitive import ComponentPhase
            from shared.infrastructure.repositories.refusal_repository import (
                RefusalRepository,
            )

            repo = RefusalRepository()
            await repo.record_refusal(
                component_id="reflexive_coder",
                phase=ComponentPhase.EXECUTION.value,
                refusal_type="extraction",
                reason="Cannot extract valid Python code from repair response.",
                suggested_action="Review error message and retry repair.",
                original_request=f"Repair: {task.step}",
                confidence=0.0,
                context_data={"pain_signal": pain_signal[:200]},
                session_id=(
                    self.tracer.session_id
                    if hasattr(self.tracer, "session_id")
                    else None
                ),
            )
            raise ValueError("Failed to extract code from repair response.")

        # PRESERVED: v2.4 Semantic Drift Detection
        alignment_score = await self._calculate_alignment(fixed_code, goal)
        if alignment_score < 0.4:
            logger.error(
                "🚨 Semantic Drift Detected! Alignment Score: %.2f", alignment_score
            )

        self.tracer.record(
            agent="ReflexiveCoder",
            decision_type="reflexive_repair",
            rationale=f"Repaired based on pain. Alignment: {alignment_score:.2f}",
            chosen_action="LLM-based logic correction",
            context={"pain": pain_signal[:200], "semantic_alignment": alignment_score},
            confidence=alignment_score,
        )

        return fixed_code

    async def _calculate_alignment(self, code: str, goal: str) -> float:
        """Measures semantic similarity."""
        try:
            v_code = await self.cognitive_service.get_embedding_for_code(code[:2000])
            v_goal = await self.cognitive_service.get_embedding_for_code(goal)
            if not v_code or not v_goal:
                return 0.5
            return sum(a * b for a, b in zip(v_code, v_goal))
        except Exception:
            return 0.5

    # ID: 1801d0a5-ded5-4f76-b85b-f6b2ce547b11
    async def validate_output(self, code: str, file_path: str) -> dict[str, Any]:
        """Perform checks on output."""
        return await validate_code_async(
            file_path,
            code,
            auditor_context=self.auditor_context,
        )
