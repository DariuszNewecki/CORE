# src/will/agents/coder_agent.py

"""
Provides the CoderAgent, a specialist AI agent responsible for all code
generation, validation, and self-correction tasks within the CORE system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.config import get_path_or_none, settings
from shared.logger import getLogger
from shared.models import ExecutionTask
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.self_correction_engine import attempt_correction
from will.orchestration.validation_pipeline import validate_code_async

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext
logger = getLogger(__name__)


# ID: f60524bd-7e84-429c-88b7-4d226487d894
class CoderAgent:
    """A specialist agent for writing, validating, and fixing code."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        auditor_context: AuditorContext,
    ):
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context
        agent_policy = settings.load("charter.policies.agent.agent_policy")
        agent_behavior = agent_policy.get("execution_agent", {})
        self.max_correction_attempts = agent_behavior.get("max_correction_attempts", 2)

    # ID: 1bb9b0c2-12e7-497c-b39b-716a7df06bdf
    async def generate_and_validate_code_for_task(
        self, task: ExecutionTask, high_level_goal: str, context_str: str
    ) -> str:
        """
        The main entry point for the CoderAgent. It orchestrates the
        generate-validate-correct loop and returns clean, validated code.

        Raises:
            Exception: If valid code cannot be produced after all attempts.
        """
        current_code = await self._generate_code_for_task(
            task, high_level_goal, context_str
        )
        for attempt in range(self.max_correction_attempts + 1):
            logger.info(f"  -> Validation attempt {attempt + 1}...")
            validation_result = await validate_code_async(
                task.params.file_path,
                current_code,
                auditor_context=self.auditor_context,
            )
            if validation_result["status"] == "clean":
                logger.info("  -> ✅ Code is constitutionally valid.")
                return validation_result["code"]
            if attempt >= self.max_correction_attempts:
                raise Exception(
                    f"Self-correction failed after {self.max_correction_attempts + 1} attempts."
                )
            logger.warning("  -> ⚠️ Code failed validation. Attempting self-correction.")
            correction_result = await self._attempt_code_correction(
                task, current_code, validation_result, high_level_goal
            )
            if correction_result.get("status") == "success":
                logger.info("  -> ✅ Self-correction generated a potential fix.")
                current_code = correction_result["code"]
            else:
                raise Exception("Self-correction failed to produce a valid fix.")
        raise Exception("Could not produce valid code after all attempts.")

    async def _generate_code_for_task(
        self, task: ExecutionTask, goal: str, context_str: str
    ) -> str:
        """Builds the prompt and calls the LLM to generate the initial code."""
        logger.info(f"✍️  Generating code for task: '{task.step}'...")
        template_path = get_path_or_none("mind.prompts.standard_task_generator")
        prompt_template = (
            template_path.read_text(encoding="utf-8")
            if template_path and template_path.exists()
            else "Implement step '{step}' for goal '{goal}' targeting {file_path}."
        )
        final_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=task.params.file_path,
            symbol_name=task.params.symbol_name or "",
        )
        enriched_prompt = self.prompt_pipeline.process(final_prompt + context_str)
        generator = await self.cognitive_service.aget_client_for_role("Coder")
        return await generator.make_request_async(
            enriched_prompt, user_id="coder_agent"
        )

    async def _attempt_code_correction(
        self, task: ExecutionTask, current_code: str, validation_result: dict, goal: str
    ) -> dict:
        """Invokes the self-correction engine for a piece of failed code."""
        correction_context = {
            "file_path": task.params.file_path,
            "code": current_code,
            "violations": validation_result["violations"],
            "original_prompt": goal,
        }
        logger.info("  -> 🧬 Invoking self-correction engine...")
        return await attempt_correction(
            correction_context, self.cognitive_service, self.auditor_context
        )
