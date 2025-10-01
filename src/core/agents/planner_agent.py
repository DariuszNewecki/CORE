# src/core/agents/planner_agent.py
"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan that can be carried out
by the ExecutionAgent.
"""

from __future__ import annotations

from typing import List

from core.agents.base_planner import build_planning_prompt, parse_and_validate_plan
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask, PlanExecutionError

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

    # ID: b918335b-60af-4132-a944-88628a3caa66
    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> List[ExecutionTask]:
        """
        Creates an execution plan from a user goal and a reconnaissance report.
        """
        max_retries = settings.model_extra.get("CORE_MAX_RETRIES", 3)

        prompt = build_planning_prompt(
            goal, self.prompt_template, reconnaissance_report
        )
        client = await self.cognitive_service.aget_client_for_role("Planner")

        for attempt in range(max_retries):
            log.info("🧠 Generating step-by-step plan from reconnaissance context...")
            response_text = await client.make_request_async(prompt)

            if response_text:
                try:
                    return parse_and_validate_plan(response_text)
                except PlanExecutionError as e:
                    log.warning(f"Plan creation attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        ) from e
        return []
