# src/will/agents/governance_mixin.py

"""
Governance Mixin for AI Agents.

Provides constitutional validation for all autonomous operations. This mixin
allows any agent in the Will layer to check governance before executing actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mind.governance.validator_service import (
    ApprovalType,
    GovernanceDecision,
    RiskTier,
    can_execute_autonomously,
)
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 707ac6e0-f83a-4b4e-ae45-f0d42989d0dd
class GovernanceContext:
    """Context information for governance decisions."""

    filepath: str
    action: str
    agent_id: str
    additional_context: dict[str, Any] | None = None


# ID: 390cb462-61a1-4a45-9c79-3a7295526d8d
class GovernanceMixin:
    """
    Mixin that adds constitutional governance to any agent.

    Usage:
        class MyAgent(GovernanceMixin):
            async def do_something(self, filepath: str):
                decision = await self.check_governance(
                    filepath, "modify_file"
                )
                if not decision.allowed:
                    return f"Blocked: {decision.rationale}"
                # ... proceed with action
    """

    # ID: 7a454566-64ca-4011-9269-5b9bcfda00bb
    async def check_governance(
        self,
        filepath: str,
        action: str,
        agent_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> GovernanceDecision:
        """
        Check if action is allowed by constitutional governance.

        Args:
            filepath: Target file path
            action: Action to perform
            agent_id: Identifier of the agent requesting action
            context: Additional context for governance decision

        Returns:
            GovernanceDecision with allowed/rationale/violations
        """
        gov_context = context or {}
        gov_context["filepath"] = filepath
        if agent_id:
            gov_context["agent_id"] = agent_id

        decision = can_execute_autonomously(filepath, action, gov_context)

        self._log_governance_decision(filepath, action, decision)

        return decision

    def _log_governance_decision(
        self, filepath: str, action: str, decision: GovernanceDecision
    ):
        """Log governance decision for audit trail."""
        if decision.allowed:
            logger.info(
                f"✅ Governance: {action} on {filepath}",
                extra={
                    "governance_decision": "allowed",
                    "risk_tier": decision.risk_tier.name,
                    "approval_type": decision.approval_type.value,
                    "filepath": filepath,
                    "action": action,
                },
            )
        else:
            logger.warning(
                f"🚫 Governance: {action} on {filepath} - BLOCKED",
                extra={
                    "governance_decision": "blocked",
                    "risk_tier": decision.risk_tier.name,
                    "filepath": filepath,
                    "action": action,
                    "violations": decision.violations,
                    "rationale": decision.rationale,
                },
            )

    # ID: 451f21b0-30b0-484d-8db4-fd4fb1a7edd5
    def format_governance_response(self, decision: GovernanceDecision) -> str:
        """Format governance decision for user display."""
        if decision.allowed:
            if decision.approval_type == ApprovalType.AUTONOMOUS:
                return "✅ Action approved for autonomous execution"
            elif decision.approval_type == ApprovalType.VALIDATION_ONLY:
                return "✅ Action approved (will validate after execution)"

        emoji = "⚠️" if decision.risk_tier == RiskTier.ELEVATED else "🚫"
        msg = f"{emoji} Action blocked by constitutional governance\n"
        msg += f"   Reason: {decision.rationale}\n"
        msg += f"   Risk Level: {decision.risk_tier.name}\n"
        approval_display = decision.approval_type.value.replace("_", " ")
        msg += f"   Required: {approval_display.title()}"

        if decision.violations:
            msg += "\n   Violations:\n"
            for violation in decision.violations:
                msg += f"      • {violation}\n"

        return msg
