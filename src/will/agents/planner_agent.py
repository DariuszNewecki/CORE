# src/will/agents/planner_agent.py

"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan that can be carried out
by the ExecutionAgent.
"""

from __future__ import annotations

from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError

from will.agents.base_planner import build_planning_prompt, parse_and_validate_plan
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 31bb8dba-f4d2-426a-8783-d09614085258
class PlannerAgent:
    """Decomposes goals into executable plans."""

    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the PlannerAgent."""
        self.cognitive_service = cognitive_service
        self.prompt_template = settings.get_path(
            "mind.prompts.planner_agent"
        ).read_text(encoding="utf-8")

    # ID: 1ea9ec86-10a3-4356-9c31-c14e53c8fed0
    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> list[ExecutionTask]:
        """
        Creates an execution plan from a user goal and a reconnaissance report.
        """
        max_retries = settings.model_extra.get("CORE_MAX_RETRIES", 3)
        prompt = build_planning_prompt(
            goal, self.prompt_template, reconnaissance_report
        )
        client = await self.cognitive_service.aget_client_for_role("Planner")
        for attempt in range(max_retries):
            logger.info(
                "🧠 Generating step-by-step plan from reconnaissance context..."
            )
            response_text = await client.make_request_async(prompt)
            if response_text:
                try:
                    return parse_and_validate_plan(response_text)
                except PlanExecutionError as e:
                    logger.warning("Plan creation attempt {attempt + 1} failed: %s", e)
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        ) from e
        return []
