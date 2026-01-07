# src/will/agents/researcher_agent.py

"""
ResearcherAgent - Negotiates context before generation.
Implements the 'Understanding precedes Action' principle.
"""

from __future__ import annotations

import json
from typing import Any

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
        client = await self.cognitive.aget_client_for_role("Planner")
        prompt = f'\n        GOAL: {goal}\n\n        CURRENT CONTEXT:\n        {current_context}\n\n        TASK:\n        Analyze the goal and the provided code.\n        Identify if any dependencies, fixtures (conftest.py), or parent classes are missing.\n\n        RESPONSE FORMAT (Strict JSON):\n        {{\n          "status": "RESEARCHING" | "READY",\n          "reasoning": "Explain why you are ready or what is missing.",\n          "requests": [\n             {{"tool": "read_file", "path": "path/to/file.py"}},\n             {{"tool": "lookup_symbol", "qualname": "ClassName"}},\n             {{"tool": "search_vectors", "query": "semantic query"}}\n          ]\n        }}\n        '
        response = await client.make_request_async(prompt, user_id="researcher_agent")
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
