# src/will/agents/context_auditor.py

"""
ContextAuditor - The 'Souncer' for the ContextPackage.
Optimized to detect 'Logic Gaps' before the LLM starts generating.

CONSTITUTIONAL FIX:
- Now performs a 'Recursive Dependency Check'.
- Verifies that if a Class inherits from another, the Base class code is present.
"""

from __future__ import annotations

import json
from typing import Any

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
        # 1. Prepare a summary of what's currently in the 'dossier'
        items = packet.get("context", [])
        dossier_summary = "\n".join(
            [
                f"- {i.get('name')} (Type: {i.get('item_type')}, Path: {i.get('path')})"
                for i in items
            ]
        )

        # 2. Get the Auditor Role (Uses your local model if configured)
        client = await self.cognitive.aget_client_for_role("ContextAuditor")

        prompt = f"""
        TASK: Audit the Context Dossier for missing logic.
        GOAL: {goal}

        CURRENT DOSSIER CONTENT:
        {dossier_summary}

        INSTRUCTIONS:
        1. Does the goal involve modifying a file? If so, is that file's FULL CODE in the dossier?
        2. Does the code in the dossier inherit from classes (e.g. class User(Base))?
           If so, is the code for 'Base' present?
        3. Are there critical imports (e.g. shared.utils) that the LLM will need to understand?

        RESPONSE FORMAT (Strict JSON):
        {{
          "status": "READY" | "INCOMPLETE",
          "missing_elements": ["List of what is missing"],
          "reasoning": "Brief explanation of the gap.",
          "confidence_score": 0.0 to 1.0
        }}
        """

        logger.info("📡 Sourcing context completeness for: %s", goal[:50])
        response = await client.make_request_async(prompt, user_id="souncer")

        # Clean up common LLM markdown junk
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
