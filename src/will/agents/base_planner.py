# src/will/agents/base_planner.py

"""
Provides shared, stateless utility functions for planner agents.
Updated to use the canonical Atomic Action Registry.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from body.atomic.registry import action_registry
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

    DYNAMICALLY discovers available actions from the Atomic Registry,
    ensuring the Planner only uses tools that actually exist in the Body.
    """
    # 1. Use the Global Singleton Registry (The Body's Capability Map)
    registry = action_registry

    # 2. Build descriptions dynamically from the source of truth
    action_descriptions = []

    # Get all registered atomic actions
    for definition in sorted(registry.list_all(), key=lambda x: x.action_id):
        # Build a clear tool description for the LLM
        desc = f"### Action: `{definition.action_id}`\n"
        desc += f"**Description:** {definition.description}\n"
        desc += f"**Impact Level:** {definition.impact_level}\n"

        # Add parameter guidance based on the category
        desc += "**Parameters:**\n"
        if "file" in definition.action_id:
            desc += "- `file_path` (string): Path to the target file.\n"
            desc += "- `code` (string, optional): Content to write.\n"

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
        return validated_plan
    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        logger.warning("Plan creation failed validation: %s", e)
        raise PlanExecutionError("Failed to create a valid plan.") from e
