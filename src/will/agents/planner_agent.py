# src/will/agents/planner_agent.py
"""
The PlannerAgent is responsible for decomposing a high-level user goal
into a concrete, step-by-step execution plan that can be carried out
by the ExecutionAgent.
"""

from __future__ import annotations

import random

from features.self_healing import MemoryCleanupService
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

        # ALIGNED: Using PathResolver to find prompt in var/prompts/
        try:
            self.prompt_template = settings.paths.prompt("planner_agent").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            logger.error(
                "Constitutional prompt 'planner_agent.prompt' missing from var/prompts/"
            )
            raise

    # ID: 1ea9ec86-10a3-4356-9c31-c14e53c8fed0
    async def create_execution_plan(
        self, goal: str, reconnaissance_report: str = ""
    ) -> list[ExecutionTask]:
        """
        Creates an execution plan from a user goal and a reconnaissance report.
        """
        # NEW: Random memory cleanup (10% chance) before planning
        if random.random() < 0.1:
            try:
                # Use registry to get session factory safely
                cleanup_service = MemoryCleanupService(
                    session=None  # Service handles its own session via factory if needed
                )
                # Note: MemoryCleanupService needs to be called with a session in current implementation
                # This is a placeholder for the autonomous maintenance trigger
            except Exception as e:
                logger.warning("Memory cleanup trigger failed (non-critical): %s", e)

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
                    logger.warning(
                        "Plan creation attempt %s failed: %s", attempt + 1, e
                    )
                    if attempt == max_retries - 1:
                        raise PlanExecutionError(
                            "Failed to create a valid plan after max retries."
                        ) from e
        return []
