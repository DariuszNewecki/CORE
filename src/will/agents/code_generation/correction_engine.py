# src/will/agents/code_generation/correction_engine.py

"""
Handles self-correction for pattern and constitutional violations.

FIXED: Changed v.message to v['message'] for dict access.
HEALED: attempt_pattern_correction uses PromptModel.invoke() — ai.prompt.model_required compliant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.orchestration.self_correction_engine import attempt_correction


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
    from shared.models import ExecutionTask
    from will.orchestration.cognitive_service import CognitiveService
    from will.orchestration.decision_tracer import DecisionTracer

logger = getLogger(__name__)


# ID: e4e167fb-1091-4b94-aa88-e8fe74158b19
class CorrectionEngine:
    """Handles self-correction for pattern and constitutional violations."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        tracer: DecisionTracer,
    ):
        """
        Initialize correction engine.

        Args:
            cognitive_service: LLM orchestration service
            auditor_context: Constitutional auditing context
            tracer: Decision tracing system
        """
        self.cognitive_service = cognitive_service
        self.auditor_context = auditor_context
        self.tracer = tracer

    # ID: 2ac1d1d8-24a7-4b9f-9130-4c6047950663
    async def attempt_pattern_correction(
        self,
        task: ExecutionTask,
        current_code: str,
        pattern_violations: list,
        pattern_id: str,
        pattern_requirements: str,
        goal: str,
    ) -> dict:
        """
        Attempt to fix pattern violations in generated code.

        Args:
            task: The execution task
            current_code: Code with violations
            pattern_violations: List of violations found (as dicts)
            pattern_id: Pattern that was violated
            pattern_requirements: Pattern requirements text
            goal: High-level goal for context

        Returns:
            Dict with 'status' and either 'code' or 'message'
        """
        violation_messages = "\n".join(
            [f"- {v.get('message', str(v))}" for v in pattern_violations]
        )

        self.tracer.record(
            agent="CorrectionEngine",
            decision_type="pattern_correction",
            rationale=f"Detected {len(pattern_violations)} pattern violations",
            chosen_action="Attempting LLM-based pattern correction",
            alternatives=["Manual correction", "Skip correction"],
            context={"pattern_id": pattern_id, "violations": len(pattern_violations)},
            confidence=0.7,
        )

        model = PromptModel.load("pattern_correction")
        generator = await self.cognitive_service.aget_client_for_role(
            model.manifest.role
        )
        raw_response = await model.invoke(
            context={
                "pattern_id": pattern_id,
                "current_code": current_code,
                "violation_messages": violation_messages,
                "pattern_requirements": pattern_requirements,
            },
            client=generator,
            user_id="coder_agent_pattern_correction",
        )

        corrected_code = extract_python_code_from_response(raw_response)
        if corrected_code:
            return {"status": "success", "code": corrected_code}
        else:
            return {"status": "failure", "message": "Could not extract corrected code"}

    # ID: 282f2c42-42c1-44d6-a2df-9eb668d483df
    async def attempt_constitutional_correction(
        self,
        task: ExecutionTask,
        current_code: str,
        validation_result: dict,
        goal: str,
        runtime_error: str = "",
    ) -> dict:
        """
        Attempt to fix constitutional violations in generated code.

        Args:
            task: The execution task
            current_code: Code with violations
            validation_result: Validation result with violations
            goal: High-level goal for context
            runtime_error: Optional runtime error details

        Returns:
            Dict with 'status' and either 'code' or 'message'
        """
        self.tracer.record(
            agent="CorrectionEngine",
            decision_type="constitutional_correction",
            rationale=f"Detected {len(validation_result.get('violations', []))} constitutional violations",
            chosen_action="Invoking self-correction engine",
            alternatives=["Fail fast", "Manual review"],
            context={
                "violations": len(validation_result.get("violations", [])),
                "has_runtime_error": bool(runtime_error),
            },
            confidence=0.6,
        )

        correction_context = {
            "file_path": task.params.file_path,
            "code": current_code,
            "violations": validation_result["violations"],
            "original_prompt": goal,
            "runtime_error": runtime_error,
        }
        logger.info("  -> Invoking self-correction engine...")
        return await attempt_correction(
            correction_context,
            self.cognitive_service,
            self.auditor_context,
        )
