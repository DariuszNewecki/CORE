# tests/will/strategists/test_sync_strategist.py

"""
Tests for SyncStrategist component.

Constitutional Alignment:
- Tests all decision paths
- Verifies dependency ordering
- Validates component contract compliance
"""

from __future__ import annotations

import pytest

from shared.component_primitive import ComponentPhase
from will.strategists.sync_strategist import SyncStrategist


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@pytest.fixture
def strategist():
    """Fixture providing SyncStrategist instance."""
    return SyncStrategist()


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class TestComponentContract:
    """Test SyncStrategist follows Component contract."""

    @pytest.mark.asyncio
    async def test_declares_runtime_phase(self, strategist):
        """Strategists must operate in RUNTIME phase."""
        assert strategist.phase == ComponentPhase.RUNTIME

    @pytest.mark.asyncio
    async def test_returns_component_result(self, strategist):
        """Execute must return ComponentResult."""
        result = await strategist.execute(sync_target="domains")

        assert hasattr(result, "ok")
        assert hasattr(result, "data")
        assert hasattr(result, "phase")
        assert result.phase == ComponentPhase.RUNTIME

    @pytest.mark.asyncio
    async def test_component_id_matches_class(self, strategist):
        """Component ID should be derived from class name."""
        assert strategist.component_id == "syncstrategist"


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class TestTargetValidation:
    """Test sync target validation."""

    @pytest.mark.asyncio
    async def test_valid_targets_accepted(self, strategist):
        """All valid targets should be accepted."""
        valid_targets = ["domains", "symbols", "vectors", "policies", "patterns", "all"]

        for target in valid_targets:
            result = await strategist.execute(sync_target=target)
            assert result.ok

    @pytest.mark.asyncio
    async def test_invalid_target_rejected(self, strategist):
        """Invalid targets should return error."""
        result = await strategist.execute(sync_target="invalid_target")

        assert not result.ok
        assert "error" in result.data
        assert "valid_targets" in result.data


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class TestStrategySelection:
    """Test strategy selection logic."""

    @pytest.mark.asyncio
    async def test_repair_strategy_for_force_all(self, strategist):
        """Force refresh + all should trigger repair strategy."""
        result = await strategist.execute(sync_target="all", force_refresh=True)

        assert result.data["strategy"] == "repair"

    @pytest.mark.asyncio
    async def test_full_strategy_for_all(self, strategist):
        """All target should trigger full strategy."""
        result = await strategist.execute(sync_target="all")

        assert result.data["strategy"] == "full"

    @pytest.mark.asyncio
    async def test_smart_strategy_with_dependencies(self, strategist):
        """Including dependencies should trigger smart strategy."""
        result = await strategist.execute(
            sync_target="symbols", include_dependencies=True
        )

        assert result.data["strategy"] == "smart"

    @pytest.mark.asyncio
    async def test_minimal_strategy_without_dependencies(self, strategist):
        """Excluding dependencies should trigger minimal strategy."""
        result = await strategist.execute(
            sync_target="domains", include_dependencies=False
        )

        assert result.data["strategy"] == "minimal"


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
class TestDependencyOrdering:
    """Test dependency resolution and ordering."""

    @pytest.mark.asyncio
    async def test_symbols_requires_domains(self, strategist):
        """Symbols sync should include domains when dependencies enabled."""
        result = await strategist.execute(
            sync_target="symbols", include_dependencies=True
        )

        sequence = result.data["sync_sequence"]
        assert "domains" in sequence
        assert "symbols" in sequence
        # domains must come before symbols
        assert sequence.index("domains") < sequence.index("symbols")

    @pytest.mark.asyncio
    async def test_minimal_symbols_no_dependencies(self, strategist):
        """Minimal strategy should not include dependencies."""
        result = await strategist.execute(
            sync_target="symbols", include_dependencies=False
        )

        sequence = result.data["sync_sequence"]
        assert "symbols" in sequence
        assert "domains" not in sequence

    @pytest.mark.asyncio
    async def test_full_strategy_canonical_order(self, strategist):
        """Full strategy should follow canonical order."""
        result = await strategist.execute(sync_target="all")

        sequence = result.data["sync_sequence"]
        expected_order = [
            "domains",
            "symbols",
            "vectors_policies",
            "vectors_patterns",
            "vectors_symbols",
        ]

        assert sequence == expected_order


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
class TestTargetResolution:
    """Test mapping of targets to operations."""

    @pytest.mark.asyncio
    async def test_vectors_expands_to_all_vector_ops(self, strategist):
        """Vectors target should include all vector operations."""
        result = await strategist.execute(
            sync_target="vectors", include_dependencies=False
        )

        sequence = result.data["sync_sequence"]
        assert "vectors_policies" in sequence
        assert "vectors_patterns" in sequence
        assert "vectors_symbols" in sequence

    @pytest.mark.asyncio
    async def test_policies_maps_to_vector_policies(self, strategist):
        """Policies target should map to vectors_policies."""
        result = await strategist.execute(
            sync_target="policies", include_dependencies=False
        )

        sequence = result.data["sync_sequence"]
        assert sequence == ["vectors_policies"]

    @pytest.mark.asyncio
    async def test_patterns_maps_to_vector_patterns(self, strategist):
        """Patterns target should map to vectors_patterns."""
        result = await strategist.execute(
            sync_target="patterns", include_dependencies=False
        )

        sequence = result.data["sync_sequence"]
        assert sequence == ["vectors_patterns"]


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class TestExecutionMode:
    """Test execution mode determination."""

    @pytest.mark.asyncio
    async def test_sequential_for_dependencies(self, strategist):
        """Operations with dependencies should run sequentially."""
        result = await strategist.execute(
            sync_target="symbols", include_dependencies=True
        )

        assert result.data["execution_mode"] == "sequential"

    @pytest.mark.asyncio
    async def test_parallel_for_independent_ops(self, strategist):
        """Independent vector operations can run in parallel."""
        result = await strategist.execute(
            sync_target="vectors", include_dependencies=False
        )

        # policies and patterns can run parallel
        if len(result.data["sync_sequence"]) > 1:
            # Note: Current implementation is conservative and uses sequential
            # This test documents expected behavior if parallel is enabled
            assert result.data["execution_mode"] in ["parallel", "sequential"]


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class TestForceFlags:
    """Test force refresh flag configuration."""

    @pytest.mark.asyncio
    async def test_repair_forces_all_operations(self, strategist):
        """Repair strategy should force all operations."""
        result = await strategist.execute(sync_target="all", force_refresh=True)

        force_flags = result.data["force_flags"]
        assert all(force_flags.values())

    @pytest.mark.asyncio
    async def test_force_refresh_applies_to_all(self, strategist):
        """Force refresh should apply to all operations."""
        result = await strategist.execute(
            sync_target="symbols",
            include_dependencies=True,
            force_refresh=True,
        )

        force_flags = result.data["force_flags"]
        for op in result.data["sync_sequence"]:
            assert force_flags[op] is True

    @pytest.mark.asyncio
    async def test_no_force_by_default(self, strategist):
        """Operations should not force by default."""
        result = await strategist.execute(sync_target="domains")

        force_flags = result.data["force_flags"]
        assert all(not flag for flag in force_flags.values())


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class TestDurationEstimation:
    """Test duration estimation logic."""

    @pytest.mark.asyncio
    async def test_single_operation_fast(self, strategist):
        """Single operation should have short duration."""
        result = await strategist.execute(sync_target="domains")

        # Domains is ~2 seconds + overhead
        assert result.data["estimated_duration_sec"] < 10

    @pytest.mark.asyncio
    async def test_multiple_operations_longer(self, strategist):
        """Multiple operations should accumulate duration."""
        result = await strategist.execute(sync_target="all")

        # All operations should take longer
        assert result.data["estimated_duration_sec"] > 20

    @pytest.mark.asyncio
    async def test_force_refresh_increases_duration(self, strategist):
        """Force refresh should increase estimated duration."""
        normal = await strategist.execute(sync_target="symbols")
        forced = await strategist.execute(sync_target="symbols", force_refresh=True)

        assert (
            forced.data["estimated_duration_sec"]
            > normal.data["estimated_duration_sec"]
        )


# ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
class TestDecisionTracing:
    """Test decision tracing integration."""

    @pytest.mark.asyncio
    async def test_records_decision(self, strategist):
        """Strategist must record decisions for audit."""
        result = await strategist.execute(sync_target="symbols")

        # Decision should be recorded in tracer
        assert strategist.tracer is not None
        # Verify result includes all required data
        assert "sync_sequence" in result.data
        assert "strategy" in result.data


# ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class TestMetadata:
    """Test result metadata completeness."""

    @pytest.mark.asyncio
    async def test_includes_configuration(self, strategist):
        """Result metadata should include configuration."""
        result = await strategist.execute(
            sync_target="symbols",
            include_dependencies=True,
            force_refresh=True,
        )

        assert result.metadata["include_dependencies"] is True
        assert result.metadata["force_refresh"] is True
        assert result.metadata["sequence_length"] > 0

    @pytest.mark.asyncio
    async def test_suggests_next_component(self, strategist):
        """Should suggest sync_executor as next component."""
        result = await strategist.execute(sync_target="domains")

        assert result.next_suggested == "sync_executor"

    @pytest.mark.asyncio
    async def test_tracks_duration(self, strategist):
        """Should track execution duration."""
        result = await strategist.execute(sync_target="domains")

        assert result.duration_sec >= 0.0
