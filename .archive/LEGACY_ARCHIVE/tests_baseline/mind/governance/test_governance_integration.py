# tests/mind/governance/test_governance_integration.py
"""
Integration Tests for Constitutional Governance System.

Tests that governance validation works correctly when integrated with agents
and commands.
"""

import pytest


pytestmark = pytest.mark.legacy


from mind.governance.validator_service import (
    ApprovalType,
    RiskTier,
    can_execute_autonomously,
)


class TestGovernanceIntegration:
    """Test governance integration with CORE systems."""

    def test_critical_path_blocked(self):
        """Critical paths must be blocked from autonomous modification."""
        decision = can_execute_autonomously(
            filepath=".intent/charter/constitution/authority.yaml", action="edit_file"
        )

        assert not decision.allowed
        assert decision.risk_tier == RiskTier.CRITICAL
        assert "boundary violation" in decision.rationale.lower()

    def test_routine_action_allowed(self):
        """Routine actions on safe paths must be allowed."""
        decision = can_execute_autonomously(
            filepath="docs/README.md", action="fix_docstring"
        )

        assert decision.allowed
        assert decision.risk_tier in [RiskTier.ROUTINE, RiskTier.STANDARD]

    def test_prohibited_action_blocked(self):
        """Prohibited actions blocked regardless of path."""
        decision = can_execute_autonomously(
            filepath="src/body/services/database.py", action="schema_migration"
        )

        assert not decision.allowed
        assert "prohibited" in decision.rationale.lower()

    def test_elevated_risk_requires_confirmation(self):
        """Elevated risk operations require human confirmation."""
        decision = can_execute_autonomously(
            filepath="src/body/core/database.py", action="refactoring"
        )

        assert not decision.allowed
        assert decision.risk_tier == RiskTier.ELEVATED
        assert decision.approval_type == ApprovalType.HUMAN_CONFIRMATION

    @pytest.mark.asyncio
    async def test_self_healing_respects_governance(self):
        """Self-healing agent respects governance boundaries."""
        from will.agents.self_healing_agent import SelfHealingAgent

        agent = SelfHealingAgent()

        decision = await agent.check_governance(
            filepath="src/mind/governance/validator_service.py", action="format_code"
        )

        assert not decision.allowed
        assert decision.risk_tier == RiskTier.CRITICAL

    @pytest.mark.asyncio
    async def test_governance_mixin_logs_decisions(self, caplog):
        """Governance mixin logs all decisions for audit."""
        from will.agents.self_healing_agent import SelfHealingAgent

        agent = SelfHealingAgent()

        await agent.check_governance(filepath="docs/README.md", action="fix_docstring")

        assert "Governance:" in caplog.text
        assert "docs/README.md" in caplog.text

    def test_governance_violation_details(self):
        """Governance violations include detailed information."""
        decision = can_execute_autonomously(
            filepath=".intent/charter/constitution/authority.yaml",
            action="edit_file",
            context={"filepath": ".intent/charter/constitution/authority.yaml"},
        )

        assert len(decision.violations) > 0
        assert any("boundary_violation" in v for v in decision.violations)

    def test_autonomous_actions_recorded(self):
        """Autonomous actions include proper approval type."""
        decision = can_execute_autonomously(
            filepath="scripts/dev/test.sh", action="fix_docstring"
        )

        if decision.allowed:
            assert decision.approval_type in [
                ApprovalType.AUTONOMOUS,
                ApprovalType.VALIDATION_ONLY,
            ]


class TestGovernanceEdgeCases:
    """Test edge cases in governance validation."""

    def test_unknown_action_defaults_conservatively(self):
        """Unknown actions default to requiring approval."""
        decision = can_execute_autonomously(
            filepath="src/body/services/new_service.py", action="unknown_action_type"
        )

        assert decision.risk_tier.value >= RiskTier.ELEVATED.value

    def test_unknown_path_defaults_conservatively(self):
        """Unknown paths default to elevated risk."""
        decision = can_execute_autonomously(
            filepath="/completely/unknown/path.py", action="fix_docstring"
        )

        assert decision.risk_tier == RiskTier.ELEVATED

    def test_context_passed_through(self):
        """Additional context is passed through validation."""
        context = {"filepath": "test.py", "custom_field": "custom_value"}

        decision = can_execute_autonomously(
            filepath="test.py", action="fix_docstring", context=context
        )

        assert decision is not None
