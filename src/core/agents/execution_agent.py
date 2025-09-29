# src/core/agents/execution_agent.py
"""
Provides functionality for the execution_agent module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from core.agents.plan_executor import PlanExecutor
from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from core.self_correction_engine import attempt_correction
from core.validation_pipeline import validate_code_async
from shared.config import get_path_or_none, settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError

if TYPE_CHECKING:
    from features.governance.audit_context import AuditorContext

log = getLogger(__name__)


# ID: 1fedacd4-8227-4216-b07a-c807bd450550
class ExecutionAgent:
    """Orchestrates the execution of a plan, including code generation and validation."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        plan_executor: PlanExecutor,
        auditor_context: "AuditorContext",
    ):
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.executor = plan_executor
        self.auditor_context = auditor_context

        agent_policy = settings.load("charter.policies.agent.agent_policy")
        agent_behavior = agent_policy.get("execution_agent", {})
        self.max_correction_attempts = agent_behavior.get("max_correction_attempts", 2)

    # ID: 6557eefd-2f5e-4904-998a-e7ad2d8d070f
    async def execute_plan(
        self,
        high_level_goal: str,
        plan: List[ExecutionTask],
        **kwargs,
    ) -> tuple[bool, str]:
        if not plan:
            return False, "Plan is empty or invalid."

        log.info("--- Starting Governed Code Generation Phase ---")
        success, error_message = await self._prepare_all_tasks(high_level_goal, plan)
        if not success:
            return False, error_message

        log.info("--- Handing off fully validated plan to Executor ---")
        try:
            await self.executor.execute_plan(plan)
            return True, "✅ Plan executed successfully."
        except PlanExecutionError as e:
            return False, f"Plan execution failed: {str(e)}"
        except Exception as e:
            log.error("An unexpected error occurred during execution.", exc_info=True)
            return False, f"An unexpected error occurred: {str(e)}"

    async def _prepare_all_tasks(
        self, high_level_goal: str, plan: List[ExecutionTask]
    ) -> tuple[bool, str]:
        for task in plan:
            log.info(f"Preparing task: '{task.step}'")
            if (
                task.action
                in ["create_file", "edit_file", "edit_function", "create_proposal"]
                and task.params.code is None
            ):
                log.info("  -> Task requires code generation. Invoking Coder agent...")
                success, message = await self._generate_and_validate_code_for_task(
                    task, high_level_goal
                )
                if not success:
                    return False, message
                log.info("  -> ✅ Code generated and validated successfully.")

        return True, ""

    async def _generate_and_validate_code_for_task(
        self, task: ExecutionTask, high_level_goal: str
    ) -> tuple[bool, str]:
        """Generates, validates, and self-corrects code for a single task."""
        current_code = await self._generate_code_for_task(task, high_level_goal)
        if not current_code:
            return False, f"Initial code generation failed for step: '{task.step}'"

        for attempt in range(self.max_correction_attempts + 1):
            log.info(f"  -> Validation attempt {attempt + 1}...")
            validation_result = await validate_code_async(
                task.params.file_path,
                current_code,
                auditor_context=self.auditor_context,
            )

            if validation_result["status"] == "clean":
                log.info("  -> ✅ Code is constitutionally valid.")
                task.params.code = validation_result["code"]
                return True, ""

            if attempt >= self.max_correction_attempts:
                return (
                    False,
                    f"Self-correction failed after {self.max_correction_attempts} attempts for step: '{task.step}'",
                )

            log.warning("  -> ⚠️ Code failed validation. Preparing for self-correction.")
            correction_result = await self._attempt_code_correction(
                task, current_code, validation_result, high_level_goal
            )

            if correction_result.get("status") == "success":
                log.info("  -> ✅ Self-correction generated a potential fix.")
                current_code = correction_result["code"]
            else:
                return (
                    False,
                    "Self-correction failed to produce a valid retry operation.",
                )

        return (
            False,
            f"Could not produce valid code for step '{task.step}' after all attempts.",
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
        log.info("  -> 🧬 Invoking self-correction engine...")
        return await attempt_correction(
            correction_context, self.cognitive_service, self.auditor_context
        )

    async def _generate_code_for_task(self, task: ExecutionTask, goal: str) -> str:
        log.info(f"✍️  Generating code for task: '{task.step}'...")
        template_path = get_path_or_none("mind.prompts.standard_task_generator")
        prompt_template = (
            template_path.read_text(encoding="utf-8")
            if template_path and template_path.exists()
            else "Implement step '{step}' for goal '{goal}' targeting {file_path}."
        )

        context_str = ""
        if self.executor.context.file_content_cache:
            context_str += "\n\n--- CONTEXT FROM PREVIOUS STEPS ---\n"
            for path, content in self.executor.context.file_content_cache.items():
                context_str += f"\n--- Contents of {path} ---\n{content}\n"
            context_str += "--- END CONTEXT ---\n"

        if task.action in ["edit_file", "edit_function"]:
            try:
                original_code = (settings.REPO_PATH / task.params.file_path).read_text(
                    encoding="utf-8"
                )
                context_str += f"\n\n--- ORIGINAL CODE for {task.params.file_path} (for refactoring) ---\n{original_code}\n--- END ORIGINAL CODE ---\n"
            except FileNotFoundError:
                log.warning(
                    f"File {task.params.file_path} not found for editing, generating from scratch."
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
            enriched_prompt, user_id="execution_agent_coder"
        )
