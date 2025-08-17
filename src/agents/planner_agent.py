# src/agents/planner_agent.py
"""
The primary agent responsible for decomposing high-level goals into executable plans.
"""
import contextvars
import json
import re
import textwrap
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.clients import OrchestratorClient
from core.prompt_pipeline import PromptPipeline
from pydantic import ValidationError
from shared.logger import getLogger

from agents.models import ExecutionTask, PlannerConfig
from agents.plan_executor import PlanExecutionError

log = getLogger(__name__)
execution_context = contextvars.ContextVar("execution_context")


class PlannerAgent:
    """Decomposes goals into plans but does not execute them."""

    def __init__(
        self,
        orchestrator_client: OrchestratorClient,
        prompt_pipeline: PromptPipeline,
        config: Optional[PlannerConfig] = None,
    ):
        """Initializes the PlannerAgent with its dependencies."""
        self.orchestrator = orchestrator_client
        self.prompt_pipeline = prompt_pipeline
        self.config = config or PlannerConfig()

    def _setup_logging_context(self, goal: str, plan_id: str):
        """Sets up a structured logging context for a planning cycle."""
        execution_context.set(
            {
                "goal": goal,
                "plan_id": plan_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """Extracts a JSON object or array from a raw text response, handling markdown blocks."""
        match = re.search(
            r"```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text, re.DOTALL
        )
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                log.warning(
                    "Found a JSON markdown block, but it contained invalid JSON."
                )
        try:
            start_index = text.find("{")
            if start_index == -1:
                start_index = text.find("[")
            if start_index == -1:
                return None
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(text[start_index:])
            return obj
        except (json.JSONDecodeError, ValueError):
            log.warning("Could not find a valid JSON object using boundary detection.")
        log.error("Failed to extract any valid JSON from the LLM response.")
        return None

    def _log_plan_summary(self, plan: List[ExecutionTask]) -> None:
        """Logs a human-readable summary of the generated execution plan."""
        log.info(f"📋 Execution Plan Summary ({len(plan)} tasks):")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. [{task.action}] {task.step}")

    def _validate_task_params(self, task: ExecutionTask):
        """Validates that a task has all required parameters for its specified action."""
        params = task.params
        required = []
        if task.action == "add_capability_tag":
            required = ["file_path", "symbol_name", "tag"]
        elif task.action == "create_file":
            required = ["file_path"]
        elif task.action == "edit_function":
            required = ["file_path", "symbol_name"]
        if not all(getattr(params, p, None) for p in required):
            raise PlanExecutionError(
                f"Task '{task.step}' is missing required parameters for action '{task.action}'."
            )

    # CAPABILITY: llm_orchestration
    def create_execution_plan(self, high_level_goal: str) -> List[ExecutionTask]:
        """Decomposes a high-level goal into a structured, code-free execution plan using an LLM."""
        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self._setup_logging_context(high_level_goal, plan_id)
        log.info("🧠 Decomposing goal into a high-level plan...")

        prompt_template = textwrap.dedent(
            """
            You are a hyper-competent, meticulous system architect AI. Your task is to decompose a high-level goal into a JSON execution plan.
            Your entire output MUST be a single, valid JSON array of objects.

            **High-Level Goal:** "{goal}"

            **Available Actions & Required Parameters:**
            - Action: `create_file` -> Params: `{{ "file_path": "<path>" }}`
            - Action: `edit_function` -> Params: `{{ "file_path": "<path>", "symbol_name": "<func_name>" }}`
            - Action: `add_capability_tag` -> Params: `{{ "file_path": "<path>", "symbol_name": "<func_name>", "tag": "<tag_name>" }}`

            **CRITICAL RULE:** Do NOT include a `"code"` parameter in this step. Generate the code-free JSON plan now.
            """
        ).strip()
        final_prompt = prompt_template.format(goal=high_level_goal)
        enriched_prompt = self.prompt_pipeline.process(final_prompt)

        for attempt in range(self.config.max_retries):
            try:
                response_text = self.orchestrator.make_request(
                    enriched_prompt, user_id="planner_agent_architect"
                )
                parsed_json = self._extract_json_from_response(response_text)
                if not parsed_json:
                    raise ValueError("No valid JSON found in response")
                if isinstance(parsed_json, dict):
                    parsed_json = [parsed_json]

                validated_plan = [ExecutionTask(**task) for task in parsed_json]
                for task in validated_plan:
                    self._validate_task_params(task)

                self._log_plan_summary(validated_plan)
                return validated_plan
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise PlanExecutionError(
                        "Failed to create a valid high-level plan after max retries."
                    )
        return []
