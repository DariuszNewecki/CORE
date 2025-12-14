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
# ID: 373bbf3b-d13e-468d-813b-5fb8de77bb59
class GovernanceContext:
    """Context information for governance decisions."""

    filepath: str
    action: str
    agent_id: str
    additional_context: dict[str, Any] | None = None


# ID: dd255352-e203-47e2-9e33-d19cf4317e62
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

    # ID: e97f31ce-2c86-4b11-b271-68bd8208d7d1
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
                "✅ Governance: %s on %s",
                action,
                filepath,
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
                "🚫 Governance: %s on %s - BLOCKED",
                action,
                filepath,
                extra={
                    "governance_decision": "blocked",
                    "risk_tier": decision.risk_tier.name,
                    "filepath": filepath,
                    "action": action,
                    "violations": decision.violations,
                    "rationale": decision.rationale,
                },
            )

    # ID: e6c46fa0-3a89-4354-892d-9be7ae047e68
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
