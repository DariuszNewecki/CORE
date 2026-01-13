# src/will/agents/micro_planner.py

"""
Specialized agent for generating safe, low-risk execution plans.
Used for A1 autonomous self-healing and micro-proposals.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'autonomy.lanes.boundary_enforcement'.
- MODERNIZATION: Uses PathResolver standard instead of settings.load().
- Traceability: Mandatory DecisionTracer integration.
"""

from __future__ import annotations

import json
from typing import Any

import yaml

from shared.config import settings
from shared.logger import getLogger
from shared.models import PlanExecutionError
from will.agents.base_planner import parse_and_validate_plan
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: f283a000-0b21-4a40-825f-2d7477bf5a12
class MicroPlannerAgent:
    """Decomposes goals into safe, auto-approvable plans."""

    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the MicroPlannerAgent."""
        self.cognitive_service = cognitive_service
        self.tracer = DecisionTracer()

        # MODERNIZATION: Resolve policy path via PathResolver (SSOT)
        try:
            # We explicitly load agent_governance to understand permitted autonomy lanes
            policy_path = settings.paths.policy("agent_governance")
            self.policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(
                "MicroPlanner: Could not load agent_governance policy: %s", e
            )
            self.policy = {}

        # ALIGNED: Using PathResolver to find prompt in var/prompts/
        try:
            self.prompt_template = settings.paths.prompt("micro_planner").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            logger.error(
                "Constitutional prompt 'micro_planner.prompt' missing from var/prompts/"
            )
            raise

    # ID: d4a1edd0-a3ea-4f8d-a937-c6e95d8d4fb1
    async def create_micro_plan(self, goal: str) -> list[dict[str, Any]]:
        """Creates a safe execution plan from a user goal."""

        # We pass the policy to the LLM so it knows the "Micro-Proposal" boundaries
        policy_content = json.dumps(self.policy, indent=2)

        final_prompt = self.prompt_template.format(
            policy_content=policy_content, user_goal=goal
        )

        planner_client = await self.cognitive_service.aget_client_for_role("Planner")

        logger.info("🤖 Micro-Planner: Designing low-risk execution strategy...")
        response_text = await planner_client.make_request_async(
            final_prompt, user_id="micro_planner_agent"
        )

        try:
            # Reuses the standard validation logic from base_planner
            plan = parse_and_validate_plan(response_text)
            micro_plan = [task.model_dump() for task in plan]

            # MANDATORY TRACING: Record the micro-decision
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="micro_task_execution",
                rationale="Formed safe, low-risk plan for autonomous self-healing",
                chosen_action=f"Generated micro-plan with {len(micro_plan)} steps",
                context={"goal": goal, "lane": "micro_proposals"},
                confidence=0.9,
            )
            return micro_plan

        except PlanExecutionError as e:
            logger.warning("Micro-planner failed to generate a valid plan: %s", e)
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="task_failure",
                rationale=str(e),
                chosen_action="Halt micro-planning",
                confidence=0.0,
            )
            return []
