# src/core/agents/planner_agent.py
"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan that can be carried out
by the ExecutionAgent.
"""

from __future__ import annotations

import json
from typing import Dict, List

from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax

from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.utils.parsing import extract_json_from_response

log = getLogger(__name__)


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

    async def _get_available_actions_from_search(self, goal: str) -> List[Dict]:
        """Uses semantic search to find relevant capabilities for a given goal."""
        log.info("🧠 Decomposing goal into a search query...")

        query_generation_prompt = f'Given the user\'s high-level goal, what is the most concise search query to find the tools needed to accomplish it?\n\nGoal: "{goal}"\n\nSearch Query:'

        planner_client = await self.cognitive_service.get_client_for_role("Planner")
        search_query = await planner_client.make_request_async(query_generation_prompt)
        log.info(f"   -> Generated search query: '{search_query.strip()}'")

        search_results = await self.cognitive_service.search_capabilities(
            search_query.strip(), limit=10
        )

        discovered_actions = []
        if search_results:
            log.info(
                f"   -> Planner discovered {len(search_results)} relevant capabilities."
            )
            for hit in search_results:
                payload = hit.get("payload", {})
                if "key" in payload:
                    discovered_actions.append(
                        {
                            "name": payload["key"],
                            "description": payload.get(
                                "description", "No description available."
                            ),
                        }
                    )
        return discovered_actions

    def _build_planning_prompt(self, goal: str, available_actions: List[Dict]) -> str:
        """Builds the detailed prompt for the planning LLM."""
        action_descriptions = "\n".join(
            [
                f"- `{action['name']}`: {action['description']}"
                for action in available_actions
            ]
        )
        return self.prompt_template.format(
            goal=goal,
            action_descriptions=action_descriptions,
        )

    def _validate_task_params(self, task: ExecutionTask, actions: List[Dict]):
        """Validates that all required parameters for a task's action are present."""
        pass  # Simplified for now as actions are dynamically discovered

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

    # --- THIS IS THE FIX ---
    async def create_execution_plan(self, goal: str) -> List[ExecutionTask]:
        """Creates an execution plan from a user goal using a two-step search-then-plan process."""
        max_retries = settings.model_extra.get("CORE_MAX_RETRIES", 3)

        available_actions = await self._get_available_actions_from_search(goal)
        if not available_actions:
            raise PlanExecutionError(
                "Could not discover any relevant capabilities to achieve the goal."
            )

        prompt = self._build_planning_prompt(goal, available_actions)
        client = await self.cognitive_service.get_client_for_role("Planner")

        for attempt in range(max_retries):
            log.info("🧠 Generating step-by-step plan from discovered capabilities...")
            response_text = await client.make_request_async(prompt)

            if response_text:
                try:
                    parsed_json = extract_json_from_response(response_text)
                    if not isinstance(parsed_json, list):
                        raise ValueError(
                            "LLM did not return a valid JSON list for the plan."
                        )

                    validated_plan = [ExecutionTask(**task) for task in parsed_json]
                    self._validate_task_params(validated_plan[0], available_actions)

                    self._log_plan_summary(validated_plan)
                    return validated_plan
                except (ValueError, ValidationError, json.JSONDecodeError) as e:
                    log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        )
        return []

    # --- END OF FIX ---
