# src/core/agents/execution_agent.py
"""
Provides functionality for the execution_agent module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from core.agents.plan_executor import PlanExecutor
from core.agents.utils import PlanExecutionContext
from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from core.self_correction_engine import attempt_correction
from core.validation_pipeline import validate_code
from features.governance.micro_proposal_validator import MicroProposalValidator
from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError

if TYPE_CHECKING:
    from features.governance.audit_context import AuditorContext


log = getLogger(__name__)


class ExecutionAgent:
    """Orchestrates the execution of a plan, including code generation and validation."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        plan_executor: PlanExecutor,
        auditor_context: "AuditorContext",
    ):
        """Initializes the ExecutionAgent with its required tools and constitutional policies."""
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.executor = plan_executor
        self.git_service = self.executor.git_service
        self.config = self.executor.config
        self.auditor_context = auditor_context
        self.validator = MicroProposalValidator()

        agent_policy = settings.load("charter.policies.agent.agent_policy")
        self.max_correction_attempts = agent_policy.get("execution_agent", {}).get(
            "max_correction_attempts", 2
        )

    def _verify_plan(self, plan: List[ExecutionTask]) -> None:
        """
        Verifies a micro-proposal plan against the constitution before execution.
        Raises PlanExecutionError if any part of the plan is invalid.
        """
        log.info(
            "🕵️  ExecutionAgent is verifying the received plan against the constitution..."
        )
        is_valid, error_message = self.validator.validate(plan)
        if not is_valid:
            raise PlanExecutionError(f"Plan validation failed: {error_message}")
        log.info("   -> ✅ Plan is constitutionally valid.")

    async def execute_plan(
        self,
        high_level_goal: str,
        plan: List[ExecutionTask],
        is_micro_proposal: bool = False,
    ) -> tuple[bool, str]:
        if not plan:
            return False, "Plan is empty or invalid."

        try:
            if is_micro_proposal:
                self._verify_plan(plan)
        except PlanExecutionError as e:
            log.error(
                f"❌ CRITICAL: Received an invalid plan. Execution aborted. Reason: {e}"
            )
            return False, str(e)

        log.info("--- Starting Governed Code Generation Phase ---")
        success, error_message = await self._generate_and_validate_all_tasks(
            high_level_goal, plan
        )
        if not success:
            return False, error_message
        log.info("--- Handing off fully validated plan to Executor ---")
        return await self._execute_validated_plan(plan)

    async def _generate_and_validate_all_tasks(
        self, high_level_goal: str, plan: List[ExecutionTask]
    ) -> tuple[bool, str]:
        for task in plan:
            log.info(f"Processing task: '{task.step}'")
            success, error_message = await self._process_single_task(
                task, high_level_goal
            )
            if not success:
                return False, error_message
        return True, ""

    async def _process_single_task(
        self, task: ExecutionTask, high_level_goal: str
    ) -> tuple[bool, str]:
        generated_code = await self._generate_code_for_task_type(task, high_level_goal)
        if not generated_code:
            if task.action not in ["create_file", "edit_function", "create_proposal"]:
                return True, ""
            return False, f"Initial code generation failed for step: '{task.step}'"
        return await self._validate_with_corrections(
            task,
            generated_code,
            high_level_goal,
        )

    async def _generate_code_for_task_type(self, task: ExecutionTask, goal: str) -> str:
        if task.action in ["create_file", "edit_function"]:
            return await self._generate_code_for_standard_task(task, goal)
        if task.action == "create_proposal":
            return await self._generate_code_for_proposal(task, goal)
        return ""

    async def _validate_with_corrections(
        self, task: ExecutionTask, initial_code: str, goal: str
    ) -> tuple[bool, str]:
        current_code = initial_code
        for attempt in range(self.max_correction_attempts + 1):
            log.info(f"  -> Validation attempt {attempt + 1}...")
            validation_result = validate_code(
                task.params.file_path,
                current_code,
                auditor_context=self.auditor_context,
            )
            if validation_result["status"] == "clean":
                log.info("  -> ✅ Code is constitutionally valid.")
                task.params.code = validation_result["code"]
                return True, ""
            if attempt >= self.max_correction_attempts:
                return False, (
                    f"Self-correction failed after {self.max_correction_attempts} "
                    f"attempts for step: '{task.step}'"
                )
            corrected_code = await self._attempt_code_correction(
                task, current_code, validation_result, goal
            )
            if corrected_code is None:
                return (
                    False,
                    "Self-correction failed to produce a valid retry operation.",
                )
            current_code = corrected_code
        return (
            False,
            f"Could not produce valid code for step '{task.step}' after all attempts.",
        )

    async def _attempt_code_correction(
        self, task: ExecutionTask, current_code: str, validation_result: dict, goal: str
    ) -> str | None:
        log.warning("  -> ⚠️ Code failed validation. Preparing for self-correction.")
        log.warning(f"     Violations: {validation_result['violations']}")
        correction_context = {
            "file_path": task.params.file_path,
            "code": current_code,
            "violations": validation_result["violations"],
            "original_prompt": goal,
        }
        log.info("  -> 🧬 Invoking self-correction engine...")
        correction_result = await attempt_correction(
            correction_context, self.cognitive_service
        )
        if correction_result.get("status") == "retry_staged":
            pending_id = correction_result.get("pending_id")
            pending_op = self.executor.file_handler.pending_writes.get(pending_id)
            if pending_op:
                log.info("  -> ✅ Self-correction generated a potential fix.")
                return pending_op["code"]
        return None

    async def _execute_validated_plan(
        self, plan: List[ExecutionTask]
    ) -> tuple[bool, str]:
        with PlanExecutionContext(self.git_service, self.config):
            try:
                await self.executor.execute_plan(plan)
                return True, "✅ Plan executed successfully."
            except PlanExecutionError as e:
                return False, f"Plan execution failed: {str(e)}"
            except Exception as e:
                log.error(
                    "An unexpected error occurred during execution.",
                    exc_info=True,
                )
                return False, f"An unexpected error occurred: {str(e)}"

    async def _generate_code_for_proposal(self, task: ExecutionTask, goal: str) -> str:
        log.info(f"✍️  Generating full file content for proposal: '{task.step}'...")
        file_path_str = task.params.file_path
        if not file_path_str:
            return ""
        original_content = self._read_existing_file(file_path_str)
        prompt_template = settings.load("mind.prompts.proposal_generator")
        final_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=file_path_str,
            original_content=original_content,
        )
        generator = await self.cognitive_service.get_client_for_role("Coder")
        return await generator.make_request_async(
            final_prompt, user_id="execution_agent_proposer"
        )

    async def _generate_code_for_standard_task(
        self, task: ExecutionTask, goal: str
    ) -> str:
        log.info(f"✍️  Generating code for task: '{task.step}'...")
        if task.action not in ["create_file", "edit_function"]:
            return ""
        prompt_template = settings.get_path(
            "mind.prompts.standard_task_generator"
        ).read_text()
        final_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=task.params.file_path,
            symbol_name=task.params.symbol_name or "",
        )
        enriched_prompt = self.prompt_pipeline.process(final_prompt)
        generator = await self.cognitive_service.get_client_for_role("Coder")
        return await generator.make_request_async(
            enriched_prompt, user_id="execution_agent_coder"
        )

    def _read_existing_file(self, file_path_str: str) -> str:
        try:
            return (settings.REPO_PATH / file_path_str).read_text(encoding="utf-8")
        except FileNotFoundError:
            log.warning(f"File {file_path_str} not found, generating from scratch.")
            return ""
        except Exception as e:
            log.error(f"Error reading {file_path_str}: {e}")
            return ""
