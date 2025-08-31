# src/agents/execution_agent.py
"""
Handles the execution of validated plans by generating required code and orchestrating task completion.
This version implements a full Generate -> Govern -> Self-Correct -> Write loop.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import List

from agents.models import ExecutionTask
from agents.plan_executor import PlanExecutionError, PlanExecutor
from agents.utils import PlanExecutionContext
from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from core.self_correction_engine import attempt_correction
from core.validation_pipeline import validate_code
from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: code_generation
class ExecutionAgent:
    """Orchestrates the execution of a plan, including code generation and validation."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        plan_executor: PlanExecutor,
    ):
        """Initializes the ExecutionAgent with its required tools."""
        self.cognitive_service = cognitive_service
        self.generator = self.cognitive_service.get_client_for_role("Coder")
        self.prompt_pipeline = prompt_pipeline
        self.executor = plan_executor
        self.git_service = self.executor.git_service
        self.config = self.executor.config

        # Load behavior policy from the constitution
        policy_path = (
            self.git_service.repo_path / ".intent/policies/agent_behavior_policy.yaml"
        )
        agent_policy = load_config(policy_path).get("execution_agent", {})
        self.max_correction_attempts = agent_policy.get("max_correction_attempts", 2)

    async def _generate_code_for_proposal(self, task: ExecutionTask, goal: str) -> str:
        """Generates the full file content for a create_proposal task."""
        log.info(f"✍️  Generating full file content for proposal: '{task.step}'...")
        file_path_str = task.params.file_path
        if not file_path_str:
            return ""

        original_content = ""
        try:
            original_content = Path(file_path_str).read_text(encoding="utf-8")
        except FileNotFoundError:
            log.warning(f"File {file_path_str} not found, generating from scratch.")
        except Exception as e:
            log.error(f"Error reading {file_path_str}: {e}")

        prompt_template = textwrap.dedent(
            """
            You are an expert Python programmer. Your task is to generate the complete, final source code for a file based on a goal.
            **Overall Goal:** {goal}
            **Current Task:** {step}
            **Target File:** {file_path}

            **Original File Content (for context):**
            ```python
            {original_content}
            ```

            **Instructions:** Your output MUST be ONLY the raw, complete, and final Python code for the entire file. Do not wrap it in markdown.
            """
        ).strip()

        final_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=file_path_str,
            original_content=original_content,
        )
        return await self.generator.make_request_async(
            final_prompt, user_id="execution_agent_proposer"
        )

    async def _generate_code_for_task(self, task: ExecutionTask, goal: str) -> str:
        """Generates the code content for a single task using a generator LLM."""
        log.info(f"✍️  Generating code for task: '{task.step}'...")
        if task.action not in ["create_file", "edit_function"]:
            return ""

        prompt_template = textwrap.dedent(
            """
            You are an expert Python programmer. Generate a single block of Python code to fulfill the task.
            **Overall Goal:** {goal}
            **Current Task:** {step}
            **Target File:** {file_path}
            **Target Symbol (if editing):** {symbol_name}
            **Instructions:** Your output MUST be ONLY the raw Python code. Do not wrap it in markdown blocks.
            """
        ).strip()

        final_prompt = prompt_template.format(
            goal=goal,
            step=task.step,
            file_path=task.params.file_path,
            symbol_name=task.params.symbol_name or "",
        )
        enriched_prompt = self.prompt_pipeline.process(final_prompt)
        return await self.generator.make_request_async(
            enriched_prompt, user_id="execution_agent_coder"
        )

    async def execute_plan(
        self, high_level_goal: str, plan: List[ExecutionTask]
    ) -> tuple[bool, str]:
        """
        Takes a plan, generates code for each step, validates it, attempts
        self-correction on failure, and then executes the fully-populated plan.
        """
        if not plan:
            return False, "Plan is empty or invalid."

        log.info("--- Starting Governed Code Generation Phase ---")
        for task in plan:
            log.info(f"Processing task: '{task.step}'")
            if task.action == "create_proposal":
                generated_code = await self._generate_code_for_proposal(
                    task, high_level_goal
                )
            else:
                generated_code = await self._generate_code_for_task(
                    task, high_level_goal
                )

            if not generated_code:
                return False, f"Initial code generation failed for step: '{task.step}'"

            current_code = generated_code
            for attempt in range(self.max_correction_attempts + 1):
                log.info(f"  -> Validation attempt {attempt + 1}...")
                validation_result = validate_code(task.params.file_path, current_code)

                if validation_result["status"] == "clean":
                    log.info("  -> ✅ Code is constitutionally valid.")
                    task.params.code = validation_result["code"]
                    break

                log.warning(
                    "  -> ⚠️ Code failed validation. Preparing for self-correction."
                )
                log.warning(f"     Violations: {validation_result['violations']}")

                if attempt >= self.max_correction_attempts:
                    return (
                        False,
                        f"Self-correction failed after {self.max_correction_attempts} attempts for step: '{task.step}'",
                    )

                correction_context = {
                    "file_path": task.params.file_path,
                    "code": current_code,
                    "violations": validation_result["violations"],
                    "original_prompt": high_level_goal,
                }

                log.info("  -> 🧬 Invoking self-correction engine...")
                correction_result = attempt_correction(
                    correction_context, self.cognitive_service
                )

                if correction_result.get("status") == "retry_staged":
                    pending_id = correction_result.get("pending_id")
                    pending_op = self.executor.file_handler.pending_writes.get(
                        pending_id
                    )
                    if pending_op:
                        log.info("  -> ✅ Self-correction generated a potential fix.")
                        current_code = pending_op["code"]
                    else:
                        return (
                            False,
                            "Self-correction failed to produce a valid retry operation.",
                        )
                else:
                    return (
                        False,
                        f"Self-correction failed: {correction_result.get('message')}",
                    )
            else:
                return (
                    False,
                    f"Could not produce valid code for step '{task.step}' after all attempts.",
                )

        log.info("--- Handing off fully validated plan to Executor ---")
        with PlanExecutionContext(self.git_service, self.config):
            try:
                await self.executor.execute_plan(plan)
                return True, "✅ Plan executed successfully."
            except PlanExecutionError as e:
                return False, f"Plan execution failed: {str(e)}"
            except Exception as e:
                log.error(
                    "An unexpected error occurred during execution.", exc_info=True
                )
                return False, f"An unexpected error occurred: {str(e)}"
