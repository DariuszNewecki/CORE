# src/will/agents/base_planner.py

"""
Provides shared, stateless utility functions for planner agents to reduce code duplication.
This serves the 'dry_by_design' constitutional principle.
"""

from __future__ import annotations

import json
import textwrap

from body.actions.registry import ActionRegistry
from pydantic import ValidationError
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
    """
    Builds the detailed prompt for a planning LLM.

    DYNAMICALLY discovers available actions from the ActionRegistry (The Body),
    ensuring the Planner (The Will) only uses tools that actually exist.
    """
    # 1. Instantiate Registry to discover actual code capabilities
    registry = ActionRegistry()

    # 2. Build descriptions dynamically from the source of truth
    action_descriptions = []

    # Sort for deterministic prompting
    for name, handler in sorted(registry._handlers.items()):
        # Use the handler's docstring as the description
        doc = textwrap.dedent(handler.__doc__ or "No description provided.").strip()

        # Build the action block
        desc = f"### Action: `{name}`\n"
        desc += f"**Description:** {doc}\n"

        # Since all handlers currently use TaskParams, we document the standard schema
        # In the future, handlers could expose their own specific schema property
        desc += "**Parameters:**\n"
        desc += "- `file_path` (string, optional): Target file.\n"
        desc += "- `code` (string, optional): Content to write or use.\n"
        desc += "- `symbol_name` (string, optional): Function/Class name to target.\n"

        action_descriptions.append(desc)

    action_descriptions_str = "\n".join(action_descriptions)

    # 3. Inject into template via Pipeline
    prompt_pipeline = PromptPipeline(settings.REPO_PATH)

    base_prompt = prompt_template.format(
        goal=goal,
        action_descriptions=action_descriptions_str,
        reconnaissance_report=reconnaissance_report,
    )

    return prompt_pipeline.process(base_prompt)


# ID: 53af1563-669b-4cd0-b636-671bdd46570d
def parse_and_validate_plan(response_text: str) -> list[ExecutionTask]:
    """Parses the LLM's JSON response and validates it into a list of ExecutionTask objects."""
    try:
        parsed_json = extract_json_from_response(response_text)
        if not isinstance(parsed_json, list):
            raise ValueError("LLM did not return a valid JSON list for the plan.")
        validated_plan = [ExecutionTask(**task) for task in parsed_json]
        logger.info(
            "PlannerAgent created execution plan with %d steps.", len(validated_plan)
        )
        for i, task in enumerate(validated_plan, 1):
            logger.info("  Step %d: %s (Action: %s)", i, task.step, task.action)

        try:
            # Log the full plan structure at DEBUG level for audit/traceability
            plan_json_str = json.dumps(
                [t.model_dump() for t in validated_plan], indent=2
            )
            logger.debug("Full Execution Plan JSON:\n%s", plan_json_str)
        except Exception:
            logger.warning("Could not serialize plan to JSON for logging.")

        return validated_plan
    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        logger.warning("Plan creation failed validation: %s", e)
        raise PlanExecutionError("Failed to create a valid plan.") from e
