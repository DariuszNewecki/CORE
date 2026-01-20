# src/will/agents/conversational_governed.py
"""
Conversational Agent with Governance Awareness.

End-user facing agent that respects constitutional governance and explains
governance decisions to users in natural language.
"""

from __future__ import annotations

from dataclasses import dataclass

from body.services.constitutional_validator import ApprovalType, RiskTier
from mind.governance.governance_mixin import GovernanceMixin
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: c9ce9ba8-0a75-4a54-8acf-b4759ab0dab9
class UserIntent:
    """Parsed user intent from natural language message."""

    message: str
    involves_files: bool
    target_file: str | None = None
    action: str | None = None


# ID: 409a44cf-dc19-4b9b-8dd1-8dca27a96e57
class ConversationalAgentGoverned(GovernanceMixin):
    """
    End-user facing agent that respects constitutional governance.

    Explains governance decisions naturally to users without technical jargon.
    """

    def __init__(self):
        """Initialize conversational agent with governance."""
        self.agent_id = "conversational_agent"

    # ID: 38878972-693f-4f94-bd8a-b23cdc9d364c
    async def process_message(self, message: str) -> str:
        """
        Process user message with governance awareness.

        Args:
            message: User's natural language message

        Returns:
            Response string explaining what happened
        """
        intent = await self._parse_intent(message)

        if intent.involves_files:
            decision = await self.check_governance(
                filepath=intent.target_file,
                action=intent.action,
                agent_id=self.agent_id,
            )

            if not decision.allowed:
                return self._explain_governance_block(decision, intent)

            if decision.approval_type == ApprovalType.VALIDATION_ONLY:
                response = await self._execute_action(intent)
                validation_msg = "\n\n✅ Action completed and validated."
                return response + validation_msg

        return await self._execute_action(intent)

    def _explain_governance_block(self, decision, intent: UserIntent) -> str:
        """
        Explain governance block to user in natural language.

        Args:
            decision: GovernanceDecision object
            intent: Parsed user intent

        Returns:
            Human-friendly explanation
        """
        explanation = "I can't do that right now. Here's why:\n\n"

        if decision.risk_tier == RiskTier.CRITICAL:
            explanation += "🚫 This operation touches critical system "
            explanation += "components that require careful human review.\n\n"
        elif decision.risk_tier == RiskTier.ELEVATED:
            explanation += "⚠️  This operation has elevated risk and needs "
            explanation += "your confirmation before I proceed.\n\n"

        explanation += f"Specifically: {decision.rationale}\n\n"

        if decision.approval_type == ApprovalType.HUMAN_CONFIRMATION:
            explanation += "Would you like me to prepare a proposal "
            explanation += "for your review?"
        else:
            explanation += "This falls under constitutional protections "
            explanation += "that prevent autonomous modifications to "
            explanation += "governance systems."

        return explanation

    async def _parse_intent(self, message: str) -> UserIntent:
        """
        Parse user intent from message.

        Args:
            message: User's natural language message

        Returns:
            Parsed intent object
        """
        # Placeholder - integrate with your existing intent parsing
        return UserIntent(message=message, involves_files=False)

    async def _execute_action(self, intent: UserIntent) -> str:
        """
        Execute approved action.

        Args:
            intent: Parsed and approved user intent

        Returns:
            Result message
        """
        # Placeholder - integrate with your existing execution logic
        return "Action executed successfully"
