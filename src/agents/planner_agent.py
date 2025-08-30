# src/agents/planner_agent.py
"""
Handles the decomposition of high-level goals into structured, code-free execution plans using LLM orchestration.
"""
from __future__ import annotations

import contextvars
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import ValidationError

from agents.models import ExecutionTask, PlannerConfig
from agents.plan_executor import PlanExecutionError

# --- MODIFICATION START ---
# from core.clients import BaseLLMClient # REMOVED THIS IMPORT
from core.cognitive_service import CognitiveService  # ADDED THIS IMPORT

# --- MODIFICATION END ---
from core.prompt_pipeline import PromptPipeline
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response

log = getLogger(__name__)
execution_context = contextvars.ContextVar("execution_context")


class PlannerAgent:
    """Decomposes goals into plans but does not execute them."""

    # --- MODIFICATION START ---
    # The __init__ signature now accepts the CognitiveService, not a specific client.
    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        context: Dict[str, Any],
    ):
        # --- MODIFICATION END ---
        """Initializes the PlannerAgent with its dependencies."""
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.context = context

        raw_config = (
            context.get("policies", {})
            .get("agent_behavior_policy", {})
            .get("planner_agent", {})
        )
        self.config = PlannerConfig(**raw_config)

    def _setup_logging_context(self, goal: str, plan_id: str):
        """Sets up a structured logging context for a planning cycle."""
        execution_context.set(
            {
                "goal": goal,
                "plan_id": plan_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _log_plan_summary(self, plan: List[ExecutionTask]) -> None:
        """Logs a human-readable summary of the generated execution plan."""
        log.info(f"📋 Execution Plan Summary ({len(plan)} tasks):")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. [{task.action}] {task.step}")

    def _validate_task_params(self, task: ExecutionTask):
        """Validates that a task has all required parameters for its specified action."""
        # ... (This method remains unchanged)
        params = task.params
        required = []
        if task.action == "add_capability_tag":
            required = ["file_path", "symbol_name", "tag"]
        elif task.action == "create_file":
            required = ["file_path"]
        elif task.action == "edit_function":
            required = ["file_path", "symbol_name"]
        elif task.action == "create_proposal":
            required = ["file_path", "justification"]
        elif task.action == "delete_file":
            required = ["file_path"]
        if not all(getattr(params, p, None) for p in required):
            raise PlanExecutionError(
                f"Task '{task.step}' is missing required parameters for action '{task.action}'."
            )

    # CAPABILITY: planning
    def create_execution_plan(self, high_level_goal: str) -> List[ExecutionTask]:
        """Decomposes a high-level goal into a structured, code-free execution plan using an LLM."""
        plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self._setup_logging_context(high_level_goal, plan_id)
        log.info("🧠 Decomposing goal into a high-level plan...")

        prompt_template = textwrap.dedent(
            """
            You are a hyper-competent, meticulous senior software architect AI.
            A reconnaissance agent has analyzed the user's goal and the codebase to produce a surgical context report.
            Your task is to use this report to create a minimal, precise, and correct JSON execution plan.

            **High-Level Goal:** "{goal}"

            ---
            **SURGICAL CONTEXT REPORT:**
            {surgical_context}
            ---

            **Available Actions:** `delete_file`, `create_proposal`

            **CRITICAL RULES:**
            1.  Base your plan **ONLY** on the information in the Surgical Context Report.
            2.  Use `delete_file` to remove obsolete source code files.
            3.  Use `create_proposal` to modify constitutional `.yaml` files.
            4.  Do not hallucinate file paths or actions. Be precise.
            5.  Your entire output MUST be a single, valid JSON array of objects.

            Generate the plan now.
            """
        ).strip()

        surgical_context = self.context.get("surgical_context", "No context provided.")
        final_prompt = prompt_template.format(
            goal=high_level_goal, surgical_context=surgical_context
        )
        enriched_prompt = self.prompt_pipeline.process(final_prompt)

        # --- MODIFICATION START ---
        # The agent now gets its own client from the service when it needs it.
        orchestrator = self.cognitive_service.get_client_for_role("Planner")
        # --- MODIFICATION END ---

        max_retries = self.config.max_retries
        for attempt in range(max_retries):
            try:
                # --- MODIFICATION START ---
                response_text = orchestrator.make_request(
                    enriched_prompt, user_id="planner_agent_architect"
                )
                # --- MODIFICATION END ---
                parsed_json = extract_json_from_response(response_text)
                if not parsed_json:
                    raise ValueError("No valid JSON found")
                if isinstance(parsed_json, dict):
                    parsed_json = [parsed_json]
                validated_plan = [ExecutionTask(**task) for task in parsed_json]
                for task in validated_plan:
                    self._validate_task_params(task)
                self._log_plan_summary(validated_plan)
                return validated_plan
            except (ValueError, ValidationError) as e:
                log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise PlanExecutionError(
                        "Failed to create a valid plan after max retries."
                    )
        return []
