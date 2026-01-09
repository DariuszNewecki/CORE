# tests/will/strategists/test_validation_strategist.py

"""
Tests for ValidationStrategist component.

Constitutional Alignment:
- Tests all decision paths
- Verifies decision tracing
- Validates component contract compliance
"""

from __future__ import annotations

import pytest

from shared.component_primitive import ComponentPhase
from will.strategists.validation_strategist import ValidationStrategist


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@pytest.fixture
def strategist():
    """Fixture providing ValidationStrategist instance."""
    return ValidationStrategist()


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class TestComponentContract:
    """Test ValidationStrategist follows Component contract."""

    @pytest.mark.asyncio
    async def test_declares_runtime_phase(self, strategist):
        """Strategists must operate in RUNTIME phase."""
        assert strategist.phase == ComponentPhase.RUNTIME

    @pytest.mark.asyncio
    async def test_returns_component_result(self, strategist):
        """Execute must return ComponentResult."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/models/user.py"
        )

        assert hasattr(result, "ok")
        assert hasattr(result, "data")
        assert hasattr(result, "phase")
        assert result.phase == ComponentPhase.RUNTIME

    @pytest.mark.asyncio
    async def test_component_id_matches_class(self, strategist):
        """Component ID should be derived from class name."""
        assert strategist.component_id == "validationstrategist"


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class TestRiskClassification:
    """Test risk tier classification logic."""

    @pytest.mark.asyncio
    async def test_critical_path_detection(self, strategist):
        """Files in .intent/ should be classified as CRITICAL."""
        result = await strategist.execute(
            operation_type="refactor", file_path=".intent/constitution/core.yaml"
        )

        assert result.data["risk_tier"] == "CRITICAL"
        assert result.data["validation_strategy"] == "critical_path"

    @pytest.mark.asyncio
    async def test_governance_critical_path(self, strategist):
        """Governance files should be classified as CRITICAL."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/mind/governance/validator_service.py",
        )

        assert result.data["risk_tier"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_elevated_risk_for_write_operations(self, strategist):
        """Write operations should be ELEVATED risk."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/models/user.py",
            write_mode=True,
        )

        assert result.data["risk_tier"] == "ELEVATED"
        assert result.data["validation_strategy"] == "comprehensive"

    @pytest.mark.asyncio
    async def test_routine_for_readonly(self, strategist):
        """Read-only operations should be ROUTINE."""
        result = await strategist.execute(
            operation_type="query", file_path="src/models/user.py", write_mode=False
        )

        assert result.data["risk_tier"] == "ROUTINE"
        assert result.data["validation_strategy"] == "minimal"


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class TestStrategySelection:
    """Test validation strategy selection logic."""

    @pytest.mark.asyncio
    async def test_minimal_strategy_for_queries(self, strategist):
        """Query operations should use minimal validation."""
        result = await strategist.execute(
            operation_type="query", file_path="src/models/user.py", write_mode=False
        )

        assert result.data["validation_strategy"] == "minimal"
        assert "syntax_validation" in result.data["required_checks"]
        assert "import_validation" in result.data["required_checks"]

    @pytest.mark.asyncio
    async def test_standard_strategy_for_normal_operations(self, strategist):
        """Standard operations should use standard validation."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/services/user.py"
        )

        assert result.data["validation_strategy"] == "standard"
        assert "constitutional_compliance" in result.data["required_checks"]
        assert "pattern_compliance" in result.data["required_checks"]

    @pytest.mark.asyncio
    async def test_comprehensive_for_elevated_risk(self, strategist):
        """Elevated risk should trigger comprehensive validation."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/models/user.py",
            write_mode=True,
        )

        assert result.data["validation_strategy"] == "comprehensive"
        assert "audit_history" in result.data["required_checks"]
        assert "complexity_analysis" in result.data["required_checks"]

    @pytest.mark.asyncio
    async def test_critical_path_strategy(self, strategist):
        """Critical operations should use critical_path strategy."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path=".intent/constitution/core.yaml",
            write_mode=True,
        )

        assert result.data["validation_strategy"] == "critical_path"
        assert "security_scan" in result.data["required_checks"]
        assert "performance_analysis" in result.data["required_checks"]
        assert "canary_deployment" in result.data["required_checks"]

    @pytest.mark.asyncio
    async def test_comprehensive_for_repeated_failures(self, strategist):
        """Operations with previous failures need extra scrutiny."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/services/user.py",
            previous_failures=3,
        )

        assert result.data["validation_strategy"] == "comprehensive"


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
class TestCheckMapping:
    """Test mapping from strategy to specific checks."""

    @pytest.mark.asyncio
    async def test_minimal_checks_subset(self, strategist):
        """Minimal strategy should only include base checks."""
        result = await strategist.execute(operation_type="query", write_mode=False)

        checks = result.data["required_checks"]
        assert "syntax_validation" in checks
        assert "import_validation" in checks
        assert len(checks) == 2

    @pytest.mark.asyncio
    async def test_standard_includes_constitutional(self, strategist):
        """Standard strategy must include constitutional checks."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/services/user.py"
        )

        checks = result.data["required_checks"]
        assert "constitutional_compliance" in checks
        assert "pattern_compliance" in checks
        assert "test_coverage" in checks

    @pytest.mark.asyncio
    async def test_test_operation_adds_execution_check(self, strategist):
        """Test operations should add test_execution check."""
        result = await strategist.execute(
            operation_type="test", file_path="tests/test_user.py"
        )

        assert "test_execution" in result.data["required_checks"]

    @pytest.mark.asyncio
    async def test_model_files_add_schema_check(self, strategist):
        """Model files should include schema validation."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/models/user.py"
        )

        assert "schema_validation" in result.data["required_checks"]


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
class TestQualityThresholds:
    """Test quality threshold determination."""

    @pytest.mark.asyncio
    async def test_minimal_threshold_lower(self, strategist):
        """Minimal strategy should have lower threshold."""
        result = await strategist.execute(operation_type="query", write_mode=False)

        assert result.data["quality_threshold"] == 0.7

    @pytest.mark.asyncio
    async def test_standard_threshold(self, strategist):
        """Standard strategy should have 0.8 threshold."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/services/user.py"
        )

        assert result.data["quality_threshold"] == 0.8

    @pytest.mark.asyncio
    async def test_comprehensive_threshold_higher(self, strategist):
        """Comprehensive strategy should have higher threshold."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/models/user.py",
            write_mode=True,
        )

        assert result.data["quality_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_critical_path_highest_threshold(self, strategist):
        """Critical path should have highest threshold."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path=".intent/constitution/core.yaml",
        )

        assert result.data["quality_threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_critical_risk_increases_threshold(self, strategist):
        """CRITICAL risk tier should increase threshold."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/mind/governance/validator_service.py",
        )

        # Base comprehensive (0.9) + CRITICAL bonus (0.05) = 0.95
        assert result.data["quality_threshold"] >= 0.9


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class TestEnforcementLevel:
    """Test enforcement level determination."""

    @pytest.mark.asyncio
    async def test_critical_always_blocks(self, strategist):
        """CRITICAL operations must block on failure."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path=".intent/constitution/core.yaml",
        )

        assert result.data["enforcement_level"] == "blocking"

    @pytest.mark.asyncio
    async def test_write_operations_block(self, strategist):
        """Write operations should block on validation failure."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/models/user.py",
            write_mode=True,
        )

        assert result.data["enforcement_level"] == "blocking"

    @pytest.mark.asyncio
    async def test_readonly_advisory(self, strategist):
        """Read-only operations can be advisory."""
        result = await strategist.execute(
            operation_type="query",
            file_path="src/models/user.py",
            write_mode=False,
        )

        assert result.data["enforcement_level"] == "advisory"


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class TestDecisionTracing:
    """Test decision tracing integration."""

    @pytest.mark.asyncio
    async def test_records_decision(self, strategist):
        """Strategist must record decisions for audit."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/models/user.py"
        )

        # Decision should be recorded in tracer
        assert strategist.tracer is not None
        # Verify result includes all required data
        assert "validation_strategy" in result.data
        assert "required_checks" in result.data
        assert "risk_tier" in result.data


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class TestMetadata:
    """Test result metadata completeness."""

    @pytest.mark.asyncio
    async def test_includes_operation_context(self, strategist):
        """Result metadata should include operation context."""
        result = await strategist.execute(
            operation_type="refactor",
            file_path="src/models/user.py",
            write_mode=True,
        )

        assert result.metadata["operation_type"] == "refactor"
        assert result.metadata["file_path"] == "src/models/user.py"
        assert result.metadata["write_mode"] is True

    @pytest.mark.asyncio
    async def test_suggests_next_component(self, strategist):
        """Should suggest ConstitutionalEvaluator as next component."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/models/user.py"
        )

        assert result.next_suggested == "constitutional_evaluator"

    @pytest.mark.asyncio
    async def test_tracks_duration(self, strategist):
        """Should track execution duration."""
        result = await strategist.execute(
            operation_type="refactor", file_path="src/models/user.py"
        )

        assert result.duration_sec >= 0.0
