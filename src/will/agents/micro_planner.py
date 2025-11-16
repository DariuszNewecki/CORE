# src/will/agents/micro_planner.py

"""
Implements the MicroPlannerAgent, a specialized agent for generating safe,
low-risk plans that can be auto-approved under the micro_proposal_policy.
"""

from __future__ import annotations

import json
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from shared.models import PlanExecutionError

from will.agents.base_planner import parse_and_validate_plan
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: f283a000-0b21-4a40-825f-2d7477bf5a12
class MicroPlannerAgent:
    """Decomposes goals into safe, auto-approvable plans."""

    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the MicroPlannerAgent."""
        self.cognitive_service = cognitive_service
        self.policy = settings.load("charter.policies.agent.micro_proposal_policy")
        self.prompt_template = settings.get_path(
            "mind.prompts.micro_planner"
        ).read_text(encoding="utf-8")

    # ID: d4a1edd0-a3ea-4f8d-a937-c6e95d8d4fb1
    async def create_micro_plan(self, goal: str) -> list[dict[str, Any]]:
        """Creates a safe execution plan from a user goal."""
        policy_content = json.dumps(self.policy, indent=2)
        final_prompt = self.prompt_template.format(
            policy_content=policy_content, user_goal=goal
        )
        planner_client = await self.cognitive_service.aget_client_for_role("Planner")
        response_text = await planner_client.make_request_async(
            final_prompt, user_id="micro_planner_agent"
        )
        try:
            plan = parse_and_validate_plan(response_text)
            return [task.model_dump() for task in plan]
        except PlanExecutionError:
            logger.warning(
                "Micro-planner did not return a valid plan. Returning empty plan."
            )
            return []
