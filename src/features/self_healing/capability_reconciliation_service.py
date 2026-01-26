# src/features/self_healing/capability_reconciliation_service.py

"""
Capability Reconciliation Service - AI-Powered Capability Analysis

CONSTITUTIONAL ALIGNMENT:
- Single Responsibility: Reconcile capabilities after refactoring
- Uses CognitiveService for AI analysis
- Returns structured reconciliation results

Extracted from complexity_service.py to separate AI reconciliation logic.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: reconciliation_service
# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
class CapabilityReconciliationService:
    """
    Reconciles capability tags after refactoring using AI analysis.

    Asks an AI Constitutionalist to analyze refactored code and determine
    how capability tags should be updated or redistributed.
    """

    def __init__(self, cognitive_service: CognitiveService):
        """
        Initialize reconciliation service.

        Args:
            cognitive_service: CognitiveService for AI operations
        """
        self.cognitive_service = cognitive_service

    # ID: reconcile_capabilities
    # ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
    async def reconcile_capabilities(
        self,
        original_code: str,
        original_capabilities: list[str],
        refactoring_plan: dict[str, str],
    ) -> dict[str, Any]:
        """
        Analyze refactoring and reconcile capability tags.

        Args:
            original_code: Original file code (for context)
            original_capabilities: Capabilities from original file
            refactoring_plan: Map of new file paths to their code

        Returns:
            Dict with 'code_modifications' and 'constitutional_amendment_proposal'
        """
        logger.info("Asking AI Constitutionalist to reconcile capabilities...")

        refactored_code_json = json.dumps(refactoring_plan, indent=2)

        prompt = (
            "You are an expert CORE Constitutionalist. You understand that a good refactoring "
            "not only improves code but also clarifies purpose.\n"
            f"The original file provided these capabilities: {original_capabilities}\n"
            f"A refactoring has occurred, resulting in these new files:\n{refactored_code_json}\n"
            "Your task is to produce a JSON object with: 'code_modifications' "
            "(file paths mapped to code with updated tags) "
            "and 'constitutional_amendment_proposal' (if new capabilities should be declared).\n"
            "Return ONLY a valid JSON object."
        )

        constitutionalist = await self.cognitive_service.aget_client_for_role("Planner")
        response = await constitutionalist.make_request_async(
            prompt, user_id="constitutionalist_agent"
        )

        try:
            reconciliation_result = extract_json_from_response(response)
            if not reconciliation_result:
                raise ValueError("No valid JSON object found.")
            return reconciliation_result
        except Exception as e:
            logger.error("Failed to parse reconciliation plan: %s", e)
            # Fallback: return original plan unchanged
            return {
                "code_modifications": refactoring_plan,
                "constitutional_amendment_proposal": None,
            }
