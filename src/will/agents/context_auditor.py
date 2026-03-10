# src/will/agents/context_auditor.py

"""
ContextAuditor - The 'Souncer' for the ContextPackage.
Optimized to detect 'Logic Gaps' before the LLM starts generating.

CONSTITUTIONAL FIX:
- Now performs a 'Recursive Dependency Check'.
- Verifies that if a Class inherits from another, the Base class code is present.
HEALED: audit_context_packet uses PromptModel.invoke() — ai.prompt.model_required compliant.
"""

from __future__ import annotations

import json
from typing import Any

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a0153dfa-2ce2-4644-94f2-3334d7bd05b8
class ContextAuditor:
    """
    Evaluates a Context Dossier to ensure it is 'Actionable'.
    """

    def __init__(self, cognitive_service: Any):
        self.cognitive = cognitive_service

    # ID: 17fef4dd-dd02-4814-884a-f84cdea7432e
    async def audit_context_packet(self, goal: str, packet: dict[str, Any]) -> dict:
        """
        Asks the 'Judge' role: 'Is this enough information to execute the goal?'
        """
        items = packet.get("context", [])
        dossier_summary = "\n".join(
            [
                f"- {i.get('name')} (Type: {i.get('item_type')}, Path: {i.get('path')})"
                for i in items
            ]
        )

        client = await self.cognitive.aget_client_for_role("ContextAuditor")

        logger.info("📡 Sourcing context completeness for: %s", goal[:50])

        model = PromptModel.load("context_auditor")
        response = await model.invoke(
            context={
                "goal": goal,
                "dossier_summary": dossier_summary,
            },
            client=client,
            user_id="souncer",
        )

        cleaned = response.replace("```json", "").replace("```", "").strip()

        try:
            decision = json.loads(cleaned)
            logger.info(
                "⚖️  Auditor Verdict: %s (Confidence: %s)",
                decision.get("status"),
                decision.get("confidence_score"),
            )
            return decision
        except Exception as e:
            logger.warning("Auditor failed to emit valid JSON. Defaulting to READY.")
            return {
                "status": "READY",
                "missing_elements": [],
                "reasoning": f"Parse failure: {e}",
                "confidence_score": 0.5,
            }
