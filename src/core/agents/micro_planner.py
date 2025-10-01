from __future__ import annotations

import json
from typing import Any, Dict, List

from core.agents.base_planning_agent import BasePlanningAgent
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response

log = getLogger("micro_planner_agent")


class MicroPlannerAgent(BasePlanningAgent):
    """Decomposes goals into safe, auto-approvable plans."""

    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the MicroPlannerAgent."""
        super().__init__(cognitive_service)

        self.policy = settings.load("charter.policies.agent.micro_proposal_policy")
        self.prompt_template = settings.get_path(
            "mind.prompts.micro_planner"
        ).read_text(encoding="utf-8")

    async def create_micro_plan(self, goal: str) -> List[Dict[str, Any]]:
        """Creates a safe execution plan from a user goal."""
        policy_content = json.dumps(self.policy, indent=2)
        final_prompt = self.prompt_template.format(
            policy_content=policy_content, user_goal=goal
        )

        response_text = await self._make_planning_request(
            final_prompt, "micro_planner_agent"
        )
        plan = extract_json_from_response(response_text)

        if isinstance(plan, list):
            return plan

        log.warning(
            "Micro-planner did not return a valid JSON list. Returning empty plan."
        )
        return []
