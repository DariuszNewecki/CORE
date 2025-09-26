# src/core/agents/planner_agent.py
"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan that can be carried out
by the ExecutionAgent.
"""

from __future__ import annotations

import json
from typing import List

from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax

from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.utils.parsing import extract_json_from_response

log = getLogger(__name__)


# ID: 8a33ab90-80db-4455-b1b8-636405897ced
class PlannerAgent:
    """Decomposes goals into executable plans."""

    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the PlannerAgent."""
        self.cognitive_service = cognitive_service
        self.prompt_template = settings.get_path(
            "mind.prompts.planner_agent"
        ).read_text(encoding="utf-8")
        self.actions_policy = settings.load(
            "charter.policies.governance.available_actions_policy"
        )
        self.prompt_pipeline = PromptPipeline(settings.REPO_PATH)

    def _build_planning_prompt(self, goal: str, reconnaissance_report: str) -> str:
        """Builds the detailed prompt for the planning LLM."""
        available_actions = self.actions_policy.get("actions", [])
        action_descriptions = "\n".join(
            [
                f"- `{action['name']}`: {action['description']}"
                for action in available_actions
            ]
        )
        base_prompt = self.prompt_template.format(
            goal=goal,
            action_descriptions=action_descriptions,
            reconnaissance_report=reconnaissance_report,
        )
        return self.prompt_pipeline.process(base_prompt)

    def _log_plan_summary(self, plan: List[ExecutionTask]):
        """Logs a human-readable summary of the execution plan."""
        console = Console()
        log.info("🧠 The PlannerAgent has created the following execution plan:")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. {task.step} (Action: {task.action})")
        log.info("🕵️ The ExecutionAgent will now carry out this plan.")
        try:
            plan_json = json.dumps([t.model_dump() for t in plan], indent=2)
            console.print(Syntax(plan_json, "json", theme="solarized-dark"))
        except Exception:
            log.warning("Could not serialize plan to JSON for logging.")

    # ID: b918335b-60af-4132-a944-88628a3caa66
    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str
    ) -> List[ExecutionTask]:
        """Creates an execution plan from a user goal and a reconnaissance report."""
        max_retries = settings.model_extra.get("CORE_MAX_RETRIES", 3)

        prompt = self._build_planning_prompt(goal, reconnaissance_report)
        client = await self.cognitive_service.get_client_for_role("Planner")

        for attempt in range(max_retries):
            log.info("🧠 Generating step-by-step plan from reconnaissance context...")
            response_text = await client.make_request_async(prompt)

            if response_text:
                try:
                    parsed_json = extract_json_from_response(response_text)
                    if not isinstance(parsed_json, list):
                        raise ValueError(
                            "LLM did not return a valid JSON list for the plan."
                        )

                    validated_plan = [ExecutionTask(**task) for task in parsed_json]
                    self._log_plan_summary(validated_plan)
                    return validated_plan
                except (ValueError, ValidationError, json.JSONDecodeError) as e:
                    log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        )
        return []
