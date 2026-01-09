# tests/will/strategists/test_fix_strategist.py

"""
Tests for FixStrategist component.

Constitutional Alignment:
- Tests all decision paths
- Verifies priority ordering
- Validates component contract compliance
"""

from __future__ import annotations

import pytest

from shared.component_primitive import ComponentPhase
from will.strategists.fix_strategist import FixStrategist


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@pytest.fixture
def strategist():
    """Fixture providing FixStrategist instance."""
    return FixStrategist()


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class TestComponentContract:
    """Test FixStrategist follows Component contract."""

    @pytest.mark.asyncio
    async def test_declares_runtime_phase(self, strategist):
        """Strategists must operate in RUNTIME phase."""
        assert strategist.phase == ComponentPhase.RUNTIME

    @pytest.mark.asyncio
    async def test_returns_component_result(self, strategist):
        """Execute must return ComponentResult."""
        result = await strategist.execute(fix_target="code_style")

        assert hasattr(result, "ok")
        assert hasattr(result, "data")
        assert hasattr(result, "phase")
        assert result.phase == ComponentPhase.RUNTIME

    @pytest.mark.asyncio
    async def test_component_id_matches_class(self, strategist):
        """Component ID should be derived from class name."""
        assert strategist.component_id == "fixstrategist"


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class TestStrategySelection:
    """Test strategy selection logic."""

    @pytest.mark.asyncio
    async def test_emergency_strategy_for_critical(self, strategist):
        """Critical threshold should trigger emergency strategy."""
        result = await strategist.execute(
            fix_target="all", severity_threshold="critical"
        )

        assert result.data["strategy"] == "emergency"
        # Emergency only includes critical fixes
        assert all(fix["priority"] == 1 for fix in result.data["fix_sequence"])

    @pytest.mark.asyncio
    async def test_constitutional_strategy_for_high(self, strategist):
        """High threshold should trigger constitutional strategy."""
        result = await strategist.execute(fix_target="all", severity_threshold="high")

        assert result.data["strategy"] == "constitutional"
        # Constitutional includes priority 1 and 2
        assert all(fix["priority"] <= 2 for fix in result.data["fix_sequence"])

    @pytest.mark.asyncio
    async def test_quality_strategy_for_medium(self, strategist):
        """Medium threshold should trigger quality strategy."""
        result = await strategist.execute(fix_target="all", severity_threshold="medium")

        assert result.data["strategy"] == "quality"
        # Quality includes priority 1, 2, and 3
        assert all(fix["priority"] <= 3 for fix in result.data["fix_sequence"])

    @pytest.mark.asyncio
    async def test_comprehensive_strategy_for_all_low(self, strategist):
        """All target with low threshold should trigger comprehensive."""
        result = await strategist.execute(fix_target="all", severity_threshold="low")

        assert result.data["strategy"] == "comprehensive"


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class TestPriorityOrdering:
    """Test priority-based ordering."""

    @pytest.mark.asyncio
    async def test_critical_fixes_first(self, strategist):
        """Critical fixes should come first in sequence."""
        result = await strategist.execute(fix_target="all")

        sequence = result.data["fix_sequence"]
        if sequence:
            # First fixes should be priority 1 (critical)
            critical_fixes = [f for f in sequence if f["priority"] == 1]
            if critical_fixes:
                assert sequence[0]["priority"] == 1

    @pytest.mark.asyncio
    async def test_priority_ascending_order(self, strategist):
        """Fix sequence should be ordered by priority (ascending)."""
        result = await strategist.execute(fix_target="all")

        sequence = result.data["fix_sequence"]
        priorities = [fix["priority"] for fix in sequence]

        # Check priorities are non-decreasing
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    async def test_style_fixes_last(self, strategist):
        """Code style fixes (priority 4) should come last."""
        result = await strategist.execute(fix_target="all")

        sequence = result.data["fix_sequence"]
        if sequence:
            style_fixes = [f for f in sequence if f["priority"] == 4]
            if style_fixes:
                # Last priority 4 fix should be at end
                last_style_idx = max(
                    i for i, f in enumerate(sequence) if f["priority"] == 4
                )
                assert all(f["priority"] <= 4 for f in sequence[last_style_idx:])


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
class TestFixTypeFiltering:
    """Test filtering by fix type."""

    @pytest.mark.asyncio
    async def test_single_fix_type(self, strategist):
        """Requesting single fix type should only include that type."""
        result = await strategist.execute(fix_target="missing_ids")

        sequence = result.data["fix_sequence"]
        assert len(sequence) == 1
        assert sequence[0]["fix_type"] == "missing_ids"

    @pytest.mark.asyncio
    async def test_auto_fix_only_filter(self, strategist):
        """Auto-fix-only should exclude non-auto-fixable fixes."""
        result = await strategist.execute(fix_target="all", auto_fix_only=True)

        sequence = result.data["fix_sequence"]
        assert all(fix["metadata"]["auto_fixable"] for fix in sequence)

    @pytest.mark.asyncio
    async def test_severity_threshold_filtering(self, strategist):
        """Severity threshold should filter out lower priority fixes."""
        result = await strategist.execute(fix_target="all", severity_threshold="high")

        sequence = result.data["fix_sequence"]
        # Only priority 1 and 2 should be included
        assert all(fix["priority"] <= 2 for fix in sequence)


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
class TestExecutionMode:
    """Test execution mode determination."""

    @pytest.mark.asyncio
    async def test_sequential_for_single_file(self, strategist):
        """Single file fixes should use sequential mode."""
        result = await strategist.execute(
            fix_target="all", file_path="src/models/user.py"
        )

        assert result.data["execution_mode"] == "sequential"

    @pytest.mark.asyncio
    async def test_batch_for_low_risk_codebase(self, strategist):
        """Low-risk auto-fixable fixes on codebase can use batch mode."""
        result = await strategist.execute(fix_target="code_style", auto_fix_only=True)

        # Code style is low risk and auto-fixable
        # Note: Current implementation may be conservative
        assert result.data["execution_mode"] in ["sequential", "batch"]


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class TestSafetyChecks:
    """Test safety check identification."""

    @pytest.mark.asyncio
    async def test_syntax_check_for_code_mods(self, strategist):
        """Code modifications should require syntax validation."""
        result = await strategist.execute(fix_target="complexity")

        assert "syntax_validation" in result.data["safety_checks"]

    @pytest.mark.asyncio
    async def test_constitutional_audit_for_structural(self, strategist):
        """Structural changes should require constitutional audit."""
        result = await strategist.execute(fix_target="header_compliance")

        assert "constitutional_audit" in result.data["safety_checks"]

    @pytest.mark.asyncio
    async def test_test_execution_for_coverage_fixes(self, strategist):
        """Test coverage fixes should require test execution."""
        result = await strategist.execute(fix_target="test_coverage")

        assert "test_execution" in result.data["safety_checks"]

    @pytest.mark.asyncio
    async def test_comprehensive_strategy_extensive_checks(self, strategist):
        """Comprehensive strategy should have extensive checks."""
        result = await strategist.execute(fix_target="all", severity_threshold="low")

        safety_checks = result.data["safety_checks"]
        # Should include multiple check types
        assert len(safety_checks) >= 3


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class TestDurationEstimation:
    """Test duration estimation logic."""

    @pytest.mark.asyncio
    async def test_single_file_faster_than_codebase(self, strategist):
        """Single file fixes should estimate shorter duration."""
        single_file = await strategist.execute(
            fix_target="complexity", file_path="src/models/user.py"
        )

        codebase = await strategist.execute(fix_target="complexity")

        assert (
            single_file.data["estimated_duration_sec"]
            < codebase.data["estimated_duration_sec"]
        )

    @pytest.mark.asyncio
    async def test_simple_fixes_fast(self, strategist):
        """Simple fixes like missing IDs should be fast."""
        result = await strategist.execute(fix_target="missing_ids")

        # Missing IDs is ~1 sec base + overhead
        assert result.data["estimated_duration_sec"] < 30

    @pytest.mark.asyncio
    async def test_complex_fixes_longer(self, strategist):
        """Complex fixes like test coverage should take longer."""
        result = await strategist.execute(fix_target="test_coverage")

        # Test coverage is ~45 sec base per file
        assert result.data["estimated_duration_sec"] > 40


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class TestFixMetadata:
    """Test fix type metadata accuracy."""

    @pytest.mark.asyncio
    async def test_fix_metadata_complete(self, strategist):
        """All fix types should have complete metadata."""
        result = await strategist.execute(fix_target="all")

        for fix in result.data["fix_sequence"]:
            metadata = fix["metadata"]
            assert "priority" in metadata
            assert "severity" in metadata
            assert "auto_fixable" in metadata
            assert "blast_radius" in metadata
            assert "avg_duration_sec" in metadata

    @pytest.mark.asyncio
    async def test_critical_fixes_priority_one(self, strategist):
        """Critical severity fixes should have priority 1."""
        result = await strategist.execute(fix_target="syntax_errors")

        if result.data["fix_sequence"]:
            fix = result.data["fix_sequence"][0]
            assert fix["severity"] == "critical"
            assert fix["priority"] == 1


# ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
class TestDecisionTracing:
    """Test decision tracing integration."""

    @pytest.mark.asyncio
    async def test_records_decision(self, strategist):
        """Strategist must record decisions for audit."""
        result = await strategist.execute(fix_target="all")

        # Decision should be recorded in tracer
        assert strategist.tracer is not None
        # Verify result includes all required data
        assert "fix_sequence" in result.data
        assert "strategy" in result.data


# ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class TestMetadata:
    """Test result metadata completeness."""

    @pytest.mark.asyncio
    async def test_includes_configuration(self, strategist):
        """Result metadata should include configuration."""
        result = await strategist.execute(
            fix_target="complexity",
            file_path="src/models/user.py",
            auto_fix_only=True,
        )

        assert result.metadata["auto_fix_only"] is True
        assert result.metadata["file_path"] == "src/models/user.py"
        assert result.metadata["sequence_length"] >= 0

    @pytest.mark.asyncio
    async def test_has_critical_fixes_flag(self, strategist):
        """Metadata should indicate if critical fixes present."""
        result = await strategist.execute(
            fix_target="all", severity_threshold="critical"
        )

        if result.data["fix_sequence"]:
            assert result.metadata["has_critical_fixes"] is True

    @pytest.mark.asyncio
    async def test_suggests_next_component(self, strategist):
        """Should suggest fix_executor as next component."""
        result = await strategist.execute(fix_target="code_style")

        assert result.next_suggested == "fix_executor"

    @pytest.mark.asyncio
    async def test_tracks_duration(self, strategist):
        """Should track execution duration."""
        result = await strategist.execute(fix_target="missing_ids")

        assert result.duration_sec >= 0.0


# ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_sequence_valid(self, strategist):
        """Empty fix sequence should be valid result."""
        result = await strategist.execute(
            fix_target="all",
            severity_threshold="critical",
            auto_fix_only=True,
        )

        # If no auto-fixable critical fixes exist, sequence can be empty
        assert result.ok
        assert isinstance(result.data["fix_sequence"], list)

    @pytest.mark.asyncio
    async def test_unknown_target_handled(self, strategist):
        """Unknown fix target should be handled gracefully."""
        result = await strategist.execute(fix_target="unknown_fix_type")

        # Should still return valid result (may be empty)
        assert result.ok
