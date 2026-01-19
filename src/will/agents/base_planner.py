# src/will/agents/base_planner.py
# ID: will.agents.base_planner
"""
Base planning utilities - Strategic Action Filter.

CONSTITUTIONAL ENHANCEMENT (V2.3):
- Enforces planning.mutation_only: plans must not contain Read/Analyze steps.
- Validates that ExecutionTask.params.code is None.
- Enforces valid file_path formats.
- Ensures separation between PLANNING and CODE_GENERATION phases.
"""

from __future__ import annotations

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
    Builds the final planning prompt with explicit Mutation-Only instructions.
    """
    from shared.config import settings

    prompt_pipeline = PromptPipeline(settings.REPO_PATH)

    # Pillar III: Explicitly instruct the Planner to be action-oriented.
    directive = """
STRATEGIC DIRECTIVE: MUTATION-ONLY PLANNING

Your execution plan MUST only contain MUTATING ACTIONS
(Create, Edit, Delete, Sync).

DO NOT include 'Read', 'Analyze', 'Inspect', or 'Understand' steps.
The CoderAgent has its own sensation layer and will read files automatically.

Keep the plan lean. Focus exclusively on the final state of the code.
"""

    base_prompt = prompt_template.format(
        goal=goal,
        action_descriptions=action_descriptions_str,
        reconnaissance_report=reconnaissance_report,
    )

    final_prompt = base_prompt + directive
    return prompt_pipeline.process(final_prompt)


# ID: 53af1563-669b-4cd0-b636-671bdd46570d
def parse_and_validate_plan(response_text: str) -> list[ExecutionTask]:
    """
    Parses and validates the execution plan against the Mutation-Only Law.
    """
    try:
        parsed_json = extract_json_from_response(response_text)
        if not isinstance(parsed_json, list):
            raise ValueError("LLM did not return a valid JSON list for the plan.")

        validated_plan: list[ExecutionTask] = []

        # Forbidden actions in an Execution Plan (belong to Reconnaissance)
        forbidden_actions = {"file.read", "inspect", "analyze", "check.audit"}

        for i, task_dict in enumerate(parsed_json, 1):
            if not isinstance(task_dict, dict):
                continue

            action = str(task_dict.get("action", "")).lower()
            step_desc = str(task_dict.get("step", "")).lower()

            # Constitutional check: mutation only
            if action in forbidden_actions or "read " in step_desc:
                logger.warning(
                    "Planner attempted to include Read/Analyze step (filtered)."
                )
                continue

            # Constitutional check: no code generation during planning
            params = task_dict.get("params") or {}
            if isinstance(params, dict) and "code" in params:
                if params.get("code"):
                    raise PlanExecutionError(
                        f"Step {i} violates planning.no_code_generation. "
                        "Code belongs in the Code Generation phase."
                    )

            # Constitutional check: valid file_path format
            if isinstance(params, dict) and "file_path" in params:
                file_path = params.get("file_path")
                if file_path and ("/ " in file_path or chr(92) in file_path):
                    raise PlanExecutionError(
                        f"Step {i} has invalid file_path format: {file_path}"
                    )

            # Validate via Pydantic model
            try:
                validated_plan.append(ExecutionTask(**task_dict))
            except ValidationError as e:
                logger.debug("Step %d failed Pydantic validation: %s", i, e)
                continue

        if not validated_plan:
            raise PlanExecutionError(
                "Planner failed to produce any valid mutation steps."
            )

        logger.info(
            "PlannerAgent formed action-oriented plan with %d mutations.",
            len(validated_plan),
        )
        return validated_plan

    except Exception as e:
        if isinstance(e, PlanExecutionError):
            raise
        logger.warning("Plan parsing failed: %s", e)
        raise PlanExecutionError("Failed to create a valid mutation-only plan.") from e
