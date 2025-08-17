# src/agents/execution_agent.py
"""
The ExecutionAgent is responsible for taking a concrete, validated execution
plan from the PlannerAgent and carrying it out. Its concerns are purely
about the "doing": generating code and running the execution tasks.
"""
import textwrap
from typing import List

from agents.models import ExecutionTask
from agents.plan_executor import PlanExecutionError, PlanExecutor
from agents.utils import PlanExecutionContext
from core.clients import GeneratorClient
from core.prompt_pipeline import PromptPipeline
from shared.logger import getLogger

log = getLogger(__name__)


class ExecutionAgent:
    """Orchestrates the execution of a plan, including code generation and validation."""

    def __init__(
        self,
        generator_client: GeneratorClient,
        prompt_pipeline: PromptPipeline,
        plan_executor: PlanExecutor,
    ):
        """Initializes the ExecutionAgent with its required tools."""
        self.generator = generator_client
        self.prompt_pipeline = prompt_pipeline
        self.executor = plan_executor

    # CAPABILITY: code_generation
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
        return self.generator.make_request(
            enriched_prompt, user_id="execution_agent_coder"
        )

    async def execute_plan(
        self, high_level_goal: str, plan: List[ExecutionTask]
    ) -> tuple[bool, str]:
        """
        Takes a plan, generates code for each step, and then executes the
        fully-populated plan.
        """
        if not plan:
            return False, "Plan is empty or invalid."

        log.info("--- Starting Code Generation Phase ---")
        for task in plan:
            task.params.code = await self._generate_code_for_task(task, high_level_goal)
            if task.action in ["create_file", "edit_function"] and not task.params.code:
                return False, f"Code generation failed for step: '{task.step}'"

        log.info("--- Handing off to Executor ---")
        with PlanExecutionContext(self):
            try:
                await self.executor.execute_plan(plan)
                return True, "✅ Plan executed successfully."
            except PlanExecutionError as e:
                error_detail = str(e)
                log.error(f"Execution failed: {error_detail}", exc_info=True)
                if e.violations:
                    log.error("Violations found:")
                    for v in e.violations:
                        log.error(
                            f"  - [{v.get('rule')}] L{v.get('line')}: {v.get('message')}"
                        )
                return False, f"Plan execution failed: {error_detail}"
            except Exception as e:
                log.error(
                    "An unexpected error occurred during execution.", exc_info=True
                )
                return False, f"An unexpected error occurred: {str(e)}"
