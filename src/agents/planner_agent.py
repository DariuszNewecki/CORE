# src/agents/planner_agent.py
"""
The PlannerAgent is responsible for decomposing a high-level user goal into a concrete,
step-by-step execution plan that can be carried out by the ExecutionAgent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax

from agents.models import ExecutionTask
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: agent.plan.error
class PlanExecutionError(Exception):
    """Custom exception for errors during plan execution."""

    pass


# CAPABILITY: planning
class PlannerAgent:
    """Decomposes goals into executable plans."""

    # CAPABILITY: agents.planner.initialize
    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the PlannerAgent."""
        self.cognitive_service = cognitive_service
        self.config = settings
        self.prompt_template = self._load_prompt_template()

    # CAPABILITY: agent.prompt.load_template
    def _load_prompt_template(self) -> str:
        """Loads the planner prompt from the constitution."""
        prompt_path = Path(self.config.MIND) / "prompts" / "planner_agent.prompt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Planner prompt not found at {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    # CAPABILITY: agent.planner.load_available_actions
    def _get_available_actions(self) -> List[Dict]:
        """Loads the available actions from the constitution."""
        actions_path = Path(self.config.MIND) / "config" / "actions.yaml"
        if not actions_path.exists():
            raise FileNotFoundError(f"Actions config not found at {actions_path}")
        with actions_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f).get("actions", [])

    # CAPABILITY: agent.planning.build_prompt
    def _build_planning_prompt(self, goal: str) -> str:
        """Builds the detailed prompt for the planning LLM."""
        available_actions = self._get_available_actions()
        action_descriptions = "\n".join(
            [
                f"- `{action['name']}`: {action['description']}"
                for action in available_actions
            ]
        )
        return self.prompt_template.format(
            goal=goal, action_descriptions=action_descriptions
        )

    # CAPABILITY: agent.planning.validate_task_parameters
    def _validate_task_params(self, task: ExecutionTask, actions: List[Dict]):
        """Validates that all required parameters for a task's action are present."""
        action_map = {action["name"]: action for action in actions}
        action_schema = action_map.get(task.action)
        if not action_schema:
            raise PlanExecutionError(f"Action '{task.action}' is not defined.")

        required_params = action_schema.get("required_parameters", [])
        # --- THIS IS THE FIX ---
        # Ensure that task.params exists before attempting to access its attributes.
        if required_params and task.params:
            for param in required_params:
                if not getattr(task.params, param, None):
                    raise PlanExecutionError(
                        f"Missing required parameter '{param}' for action '{task.action}'"
                    )
        # --- END OF FIX ---

    # CAPABILITY: agent.planning.log_summary
    def _log_plan_summary(self, plan: List[ExecutionTask]):
        """Logs a human-readable summary of the execution plan."""
        console = Console()
        log.info("🧠 The PlannerAgent has created the following execution plan:")
        for i, task in enumerate(plan, 1):
            log.info(f"  {i}. {task.step} (Action: {task.action})")
        log.info("🕵️ The ExecutionAgent will now carry out this plan.")
        try:
            plan_json = json.dumps([task.model_dump() for task in plan], indent=2)
            console.print(Syntax(plan_json, "json", theme="solarized-dark"))
        except Exception:
            log.warning("Could not serialize plan to JSON for logging.")

    # CAPABILITY: planning.execution.create
    def create_execution_plan(self, goal: str) -> List[ExecutionTask]:
        """Creates an execution plan from a user goal."""
        max_retries = getattr(self.config, "CORE_MAX_RETRIES", 3)
        prompt = self._build_planning_prompt(goal)
        client = self.cognitive_service.get_client_for_role("Planner")
        available_actions = self._get_available_actions()

        for attempt in range(max_retries):
            log.info("🧠 Decomposing goal into a high-level plan...")
            response_text = client.make_request(prompt)

            if response_text:
                try:
                    json_match = response_text[
                        response_text.find("[") : response_text.rfind("]") + 1
                    ]
                    if not json_match:
                        raise ValueError("No valid JSON array found in LLM response")

                    parsed_json = json.loads(json_match)
                    if isinstance(parsed_json, dict):
                        parsed_json = [parsed_json]

                    validated_plan = [ExecutionTask(**task) for task in parsed_json]
                    for task in validated_plan:
                        self._validate_task_params(task, available_actions)

                    self._log_plan_summary(validated_plan)
                    return validated_plan
                except (ValueError, ValidationError, json.JSONDecodeError) as e:
                    log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        )
        return []
