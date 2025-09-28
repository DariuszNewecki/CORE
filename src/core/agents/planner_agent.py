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

    # --- START OF AMENDMENT ---
    def _build_planning_prompt(self, goal: str, reconnaissance_report: str) -> str:
        """Builds the detailed prompt for the planning LLM."""
        available_actions = self.actions_policy.get("actions", [])

        action_descriptions = []
        for action in available_actions:
            desc = f"### Action: `{action['name']}`\n"
            desc += f"**Description:** {action['description']}\n"

            params = action.get("parameters", [])
            if params:
                desc += "**Parameters:**\n"
                for param in params:
                    req_str = (
                        "(required)" if param.get("required", False) else "(optional)"
                    )
                    desc += f"- `{param['name']}` ({param.get('type', 'any')} {req_str}): {param.get('description', '')}\n"
            action_descriptions.append(desc)

        action_descriptions_str = "\n".join(action_descriptions)

        base_prompt = self.prompt_template.format(
            goal=goal,
            action_descriptions=action_descriptions_str,
            reconnaissance_report=reconnaissance_report,
        )

        # Hard rule to avoid schema drift: ensure path-like params are named exactly 'file_path'
        rules_appendix = (
            "\n\n---\n"
            "STRICT RULES FOR ACTION PARAMETERS:\n"
            "1) Use parameter names EXACTLY as listed above.\n"
            "2) Any path-like parameter MUST be named `file_path` (never `path`).\n"
            "3) Return ONLY a JSON array of steps; no extra text.\n"
        )

        return self.prompt_pipeline.process(base_prompt + rules_appendix)

    # --- END OF AMENDMENT ---

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

    @staticmethod
    def _normalize_parameters(task_dict: dict) -> dict:
        """
        Normalize parameter names to align with the governance policy:
        - Rename 'path' -> 'file_path' when needed.
        """
        params = task_dict.get("parameters") or task_dict.get("params")
        if isinstance(params, dict):
            if "path" in params and "file_path" not in params:
                params["file_path"] = params.pop("path")
            # keep a single canonical field name for pydantic model
            task_dict["params"] = params
            task_dict.pop("parameters", None)
        return task_dict

    # ID: b918335b-60af-4132-a944-88628a3caa66
    def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> List[ExecutionTask]:
        """
        Creates an execution plan from a user goal and a reconnaissance report.

        NOTE: synchronous by design because unit tests call it directly and
        mock a synchronous `.make_request()` client.
        """
        max_retries = settings.model_extra.get("CORE_MAX_RETRIES", 3)

        prompt = self._build_planning_prompt(goal, reconnaissance_report)
        client = self.cognitive_service.get_client_for_role("Planner")

        for attempt in range(max_retries):
            log.info("🧠 Generating step-by-step plan from reconnaissance context...")
            response_text = client.make_request(prompt)

            if response_text:
                try:
                    parsed_json = extract_json_from_response(response_text)
                    if not isinstance(parsed_json, list):
                        raise ValueError(
                            "LLM did not return a valid JSON list for the plan."
                        )

                    # Normalize each step BEFORE pydantic validation to avoid drift (path -> file_path)
                    normalized_steps = [
                        (
                            self._normalize_parameters(step)
                            if isinstance(step, dict)
                            else step
                        )
                        for step in parsed_json
                    ]

                    validated_plan = [
                        ExecutionTask(**task) for task in normalized_steps
                    ]
                    self._log_plan_summary(validated_plan)
                    return validated_plan
                except (ValueError, ValidationError, json.JSONDecodeError) as e:
                    log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        )
        return []
