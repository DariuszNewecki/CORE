# src/will/agents/base_planner.py
# ID: will.agents.base_planner

"""
Base planning utilities shared across planner implementations.

CONSTITUTIONAL ENHANCEMENT:
- Validates that ExecutionTask.params.code is None (planning.no_code_generation)
- Validates file_path format (planning.file_path_validation)
- Ensures separation between PLANNING and CODE_GENERATION phases
- FIXED: Only checks params for code patterns, not descriptions
- ENHANCED: Validates that required action parameters are present
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError
from shared.utils.parsing import extract_json_from_response
from will.orchestration.prompt_pipeline import PromptPipeline


logger = getLogger(__name__)


# ID: c2df9e04-5177-44a0-bbcc-abbe0e1f7dde
def build_planning_prompt(
    goal: str,
    action_descriptions_str: str,
    reconnaissance_report: str,
    prompt_template: str,
) -> str:
    """
    Builds the final planning prompt.
    Inject into template via Pipeline
    """
    from shared.config import settings

    prompt_pipeline = PromptPipeline(settings.REPO_PATH)

    base_prompt = prompt_template.format(
        goal=goal,
        action_descriptions=action_descriptions_str,
        reconnaissance_report=reconnaissance_report,
    )

    return prompt_pipeline.process(base_prompt)


# ID: 53af1563-669b-4cd0-b636-671bdd46570d
def parse_and_validate_plan(response_text: str) -> list[ExecutionTask]:
    """
    Parses the LLM's JSON response and validates it into a list of ExecutionTask objects.

    CONSTITUTIONAL VALIDATION:
    - Enforces planning.no_code_generation: params.code must be None
    - Enforces planning.file_path_validation: file_path must be valid format
    - Enforces planning.conceptual_only: no code patterns in params (FIXED: only checks params, not descriptions)
    - Enforces planning.required_params: all required action parameters must be present
    """
    try:
        parsed_json = extract_json_from_response(response_text)
        if not isinstance(parsed_json, list):
            raise ValueError("LLM did not return a valid JSON list for the plan.")

        validated_plan = []

        for i, task_dict in enumerate(parsed_json, 1):
            # CONSTITUTIONAL CHECK 1: No code in params
            if "params" in task_dict and "code" in task_dict["params"]:
                code_value = task_dict["params"]["code"]
                if code_value is not None and code_value != "":
                    raise PlanExecutionError(
                        f"Constitutional violation in step {i}: planning.no_code_generation - "
                        f"ExecutionTask.params.code must be None. "
                        f"Code generation belongs in CODE_GENERATION phase, not PLANNING phase. "
                        f"Found: {code_value[:100]}..."
                    )

            # CONSTITUTIONAL CHECK 2: Valid file_path format
            if "params" in task_dict and "file_path" in task_dict["params"]:
                file_path = task_dict["params"]["file_path"]
                if file_path:
                    # Check for invalid patterns
                    if " / " in file_path or "\\" in file_path:
                        raise PlanExecutionError(
                            f"Constitutional violation in step {i}: planning.file_path_validation - "
                            f"Invalid file_path format: '{file_path}'. "
                            f"Paths must not contain ' / ' (spaces around slashes) or backslashes. "
                            f"Expected format: 'src/foo/bar.py'"
                        )

                    # Check for valid format
                    if not re.match(
                        r"^(src|tests|docs)/[a-zA-Z0-9_/]+\.py$", file_path
                    ):
                        logger.warning(
                            "Step %d has unusual file_path format: %s (expected src/foo/bar.py)",
                            i,
                            file_path,
                        )

            # CONSTITUTIONAL CHECK 3: No code patterns in task params
            # FIXED: Only check params dict, not the entire task (which includes descriptions)
            params_dict = task_dict.get("params", {})
            params_str = json.dumps(params_dict)

            code_patterns = [
                "def ",
                "class ",
                "import ",
                "from ",
                "async def",
                "return ",
            ]
            found_patterns = [p for p in code_patterns if p in params_str]

            if found_patterns:
                raise PlanExecutionError(
                    f"Constitutional violation in step {i}: planning.conceptual_only - "
                    f"Plan params contains code patterns: {found_patterns}. "
                    f"Planning must be conceptual only. Code belongs in CODE_GENERATION phase."
                )

            # CONSTITUTIONAL CHECK 4: Required parameters present
            # Actions declare their required parameters through function signatures.
            # The Planner MUST provide all required params.
            from body.atomic.registry import action_registry
            from will.agents.action_introspection import introspect_action_parameters

            action_id = task_dict.get("action")
            action_def = action_registry.get(action_id)

            if action_def:
                param_info = introspect_action_parameters(action_def)
                required_params = param_info["required_params"]

                provided_params = set(task_dict.get("params", {}).keys())
                missing_params = set(required_params) - provided_params

                if missing_params:
                    raise PlanExecutionError(
                        f"Constitutional violation in step {i}: planning.required_params - "
                        f"Action '{action_id}' requires parameters: {sorted(missing_params)}. "
                        f"Provided params: {sorted(provided_params) if provided_params else 'none'}. "
                        f"The Planner must discover action requirements through introspection "
                        f"and provide all required parameters."
                    )
            else:
                # Action not found - will be caught by execution, but log warning
                logger.warning("Step %d references unknown action: %s", i, action_id)

            # Validate Pydantic model
            validated_plan.append(ExecutionTask(**task_dict))

        logger.info(
            "PlannerAgent created execution plan with %d steps (constitutional validation passed).",
            len(validated_plan),
        )
        return validated_plan

    except (ValueError, ValidationError, json.JSONDecodeError) as e:
        logger.warning("Plan creation failed validation: %s", e)
        raise PlanExecutionError("Failed to create a valid plan.") from e
