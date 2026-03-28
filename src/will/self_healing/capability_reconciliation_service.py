# src/will/self_healing/capability_reconciliation_service.py

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

from shared.ai.prompt_model import PromptModel
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response


if TYPE_CHECKING:
    from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 2b423503-a4c6-4804-92b3-d6e85110200f
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
        self.capability_reconciliation_model = PromptModel.load(
            "capability_reconciliation_prompt"
        )

    # ID: f8e700ad-c95b-4147-853e-0cab4b86339a
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

        constitutionalist = await self.cognitive_service.aget_client_for_role(
            self.capability_reconciliation_model.manifest.role
        )
        response = await self.capability_reconciliation_model.invoke(
            context={
                "original_capabilities": original_capabilities,
                "refactored_code_json": refactored_code_json,
            },
            client=constitutionalist,
            user_id="constitutionalist_agent",
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
