# src/will/agents/researcher_agent.py

"""
ResearcherAgent - Negotiates context before generation.
Implements the 'Understanding precedes Action' principle.
HEALED: evaluate_readiness uses PromptModel.invoke() — ai.prompt.model_required compliant.
"""

from __future__ import annotations

import json
from typing import Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from will.orchestration.decision_tracer import DecisionTracer


logger = getLogger(__name__)


# ID: a62c8322-3406-49c7-bc4a-eac5b045e31a
class ResearcherAgent:
    def __init__(self, cognitive_service: Any):
        self.cognitive = cognitive_service
        self.tracer = DecisionTracer()

    # ID: cf936cde-5c0f-4347-a226-757db9f51800
    async def evaluate_readiness(self, goal: str, current_context: str) -> dict:
        """
        Analyzes the goal and determines if context is sufficient.
        """
        model = PromptModel.load("researcher_readiness")
        client = await self.cognitive.aget_client_for_role(model.manifest.role)
        response = await model.invoke(
            context={
                "goal": goal,
                "current_context": current_context,
            },
            client=client,
            user_id="researcher_agent",
        )

        cleaned = response.replace("```json", "").replace("```", "").strip()
        try:
            decision = json.loads(cleaned)
            self.tracer.record(
                agent="ResearcherAgent",
                decision_type="context_negotiation",
                rationale=decision.get("reasoning", "Negotiating context"),
                chosen_action=decision.get("status"),
                context=decision,
            )
            return decision
        except Exception as e:
            logger.error("Researcher failed to emit JSON: %s", e)
            return {
                "status": "READY",
                "reasoning": "Fallback due to parse error",
                "requests": [],
            }
