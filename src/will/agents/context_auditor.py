# src/will/agents/context_auditor.py

"""
ContextAuditor - The 'Souncer' for the ContextPackage.
Optimized for 3B models to detect context gaps.
"""

from __future__ import annotations

import json
from typing import Any

from will.orchestration.decision_tracer import DecisionTracer


# ID: a0153dfa-2ce2-4644-94f2-3334d7bd05b8
class ContextAuditor:
    def __init__(self, cognitive_service: Any):
        self.cognitive = cognitive_service
        self.tracer = DecisionTracer()

    # ID: 17fef4dd-dd02-4814-884a-f84cdea7432e
    async def audit_dossier(self, goal: str, dossier_summary: str) -> dict:
        """
        Asks: 'Do I have the logic for my dependencies?'
        """
        # We use a dedicated role for the local 3B model
        client = await self.cognitive.aget_client_for_role("ContextAuditor")

        prompt = f"""
        TASK: Audit the Context Dossier for missing logic.
        GOAL: {goal}

        DOSSIER SUMMARY:
        {dossier_summary}

        INSTRUCTIONS:
        1. Look for inherited classes (e.g. class User(Base)) where 'Base' is not in the dossier.
        2. Look for imported modules used in the goal where code is missing.
        3. Look for 'conftest.py' if the goal involves database tests.

        RESPONSE FORMAT (Strict JSON):
        {{
          "status": "READY" | "INCOMPLETE",
          "missing_paths": ["path/to/missing_file.py"],
          "reasoning": "Brief explanation of the gap."
        }}
        """

        response = await client.make_request_async(prompt, user_id="souncer")
        cleaned = response.replace("```json", "").replace("```", "").strip()

        try:
            decision = json.loads(cleaned)
            return decision
        except Exception:
            return {
                "status": "READY",
                "missing_paths": [],
                "reasoning": "Parse failure",
            }
