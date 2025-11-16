# src/will/agents/base_planner.py

"""
Provides shared, stateless utility functions for planner agents to reduce code duplication.
This serves the 'dry_by_design' constitutional principle.
"""

from __future__ import annotations

import json

from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax
from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.utils.parsing import extract_json_from_response

from will.orchestration.prompt_pipeline import PromptPipeline

logger = getLogger(__name__)


# ID: 9fbb8e8b-4d4e-46db-8bb1-73be88f961a9
def build_planning_prompt(
    goal: str, prompt_template: str, reconnaissance_report: str
) -> str:
    """Builds the detailed prompt for a planning LLM, including available actions."""
    actions_policy = settings.load(
        "charter.policies.governance.available_actions_policy"
    )
    available_actions = actions_policy.get("actions", [])
    prompt_pipeline = PromptPipeline(settings.REPO_PATH)
    action_descriptions = []
    for action in available_actions:
        desc = f"### Action: `{action['name']}`\n"
        desc += f"**Description:** {action['description']}\n"
        params = action.get("parameters", [])
        if params:
            desc += "**Parameters:**\n"
            for param in params:
                req_str = "(required)" if param.get("required", False) else "(optional)"
                desc += f"- `{param['name']}` ({param.get('type', 'any')} {req_str}): {param.get('description', '')}\n"
        action_descriptions.append(desc)
    action_descriptions_str = "\n".join(action_descriptions)
    base_prompt = prompt_template.format(
        goal=goal,
        action_descriptions=action_descriptions_str,
        reconnaissance_report=reconnaissance_report,
    )
    return prompt_pipeline.process(base_prompt)


# ID: 53af1563-669b-4cd0-b636-671bdd46570d
def parse_and_validate_plan(response_text: str) -> list[ExecutionTask]:
    """Parses the LLM's JSON response and validates it into a list of ExecutionTask objects."""
    console = Console()
    try:
        parsed_json = extract_json_from_response(response_text)
        if not isinstance(parsed_json, list):
            raise ValueError("LLM did not return a valid JSON list for the plan.")
        validated_plan = [ExecutionTask(**task) for task in parsed_json]
        logger.info("🧠 The PlannerAgent has created the following execution plan:")
        for i, task in enumerate(validated_plan, 1):
            logger.info(f"  {i}. {task.step} (Action: {task.action})")
        logger.info("🕵️ The ExecutionAgent will now carry out this plan.")
        try:
            plan_json_str = json.dumps(
                [t.model_dump() for t in validated_plan], indent=2
            )
            console.print(Syntax(plan_json_str, "json", theme="solarized-dark"))
        except Exception:
            logger.warning("Could not serialize plan to JSON for logging.")
        return validated_plan
    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        logger.warning(f"Plan creation failed validation: {e}")
        raise PlanExecutionError("Failed to create a valid plan.") from e
