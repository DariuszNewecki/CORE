# tests/body/evaluators/test_performance_evaluator.py

"""
Tests for PerformanceEvaluator component.

Constitutional Alignment:
- Tests evaluation accuracy
- Verifies threshold enforcement
- Validates component contract compliance
"""

from __future__ import annotations

import pytest

from body.evaluators.performance_evaluator import PerformanceEvaluator
from shared.component_primitive import ComponentPhase


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@pytest.fixture
def evaluator():
    """Fixture providing PerformanceEvaluator instance."""
    return PerformanceEvaluator()


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class TestComponentContract:
    """Test PerformanceEvaluator follows Component contract."""

    @pytest.mark.asyncio
    async def test_declares_audit_phase(self, evaluator):
        """Evaluators must operate in AUDIT phase."""
        assert evaluator.phase == ComponentPhase.AUDIT

    @pytest.mark.asyncio
    async def test_returns_component_result(self, evaluator):
        """Execute must return ComponentResult."""
        result = await evaluator.execute(operation_type="query", duration_sec=0.5)

        assert hasattr(result, "ok")
        assert hasattr(result, "data")
        assert hasattr(result, "phase")
        assert result.phase == ComponentPhase.AUDIT

    @pytest.mark.asyncio
    async def test_component_id_matches_class(self, evaluator):
        """Component ID should be derived from class name."""
        assert evaluator.component_id == "performanceevaluator"


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class TestDurationEvaluation:
    """Test duration threshold checking."""

    @pytest.mark.asyncio
    async def test_duration_within_threshold_passes(self, evaluator):
        """Duration within threshold should pass."""
        result = await evaluator.execute(
            operation_type="query", duration_sec=0.5  # Threshold is 1s
        )

        assert result.ok
        assert len(result.data["issues"]) == 0

    @pytest.mark.asyncio
    async def test_duration_exceeds_threshold_fails(self, evaluator):
        """Duration exceeding threshold should fail."""
        result = await evaluator.execute(
            operation_type="query", duration_sec=2.0  # Threshold is 1s
        )

        assert not result.ok
        assert any(issue["type"] == "duration" for issue in result.data["issues"])

    @pytest.mark.asyncio
    async def test_duration_issue_includes_overhead(self, evaluator):
        """Duration issues should calculate overhead percentage."""
        result = await evaluator.execute(
            operation_type="query", duration_sec=2.0  # 100% over threshold
        )

        duration_issue = next(
            i for i in result.data["issues"] if i["type"] == "duration"
        )
        assert "overhead_percent" in duration_issue
        assert duration_issue["overhead_percent"] == pytest.approx(100.0, rel=0.1)


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class TestMemoryEvaluation:
    """Test memory threshold checking."""

    @pytest.mark.asyncio
    async def test_memory_within_threshold_passes(self, evaluator):
        """Memory within threshold should pass."""
        result = await evaluator.execute(
            operation_type="query", memory_mb=30  # Threshold is 50MB
        )

        assert result.ok
        assert not any(issue["type"] == "memory" for issue in result.data["issues"])

    @pytest.mark.asyncio
    async def test_memory_exceeds_threshold_fails(self, evaluator):
        """Memory exceeding threshold should fail."""
        result = await evaluator.execute(
            operation_type="query", memory_mb=100  # Threshold is 50MB
        )

        assert not result.ok
        assert any(issue["type"] == "memory" for issue in result.data["issues"])


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
class TestIOEvaluation:
    """Test I/O operations threshold checking."""

    @pytest.mark.asyncio
    async def test_io_within_threshold_passes(self, evaluator):
        """I/O operations within threshold should pass."""
        result = await evaluator.execute(
            operation_type="validation", io_operations=50  # Threshold is 100
        )

        assert result.ok

    @pytest.mark.asyncio
    async def test_io_exceeds_threshold_fails(self, evaluator):
        """I/O operations exceeding threshold should fail."""
        result = await evaluator.execute(
            operation_type="validation", io_operations=200  # Threshold is 100
        )

        assert not result.ok
        assert any(issue["type"] == "io" for issue in result.data["issues"])


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
class TestOperationTypeThresholds:
    """Test threshold selection by operation type."""

    @pytest.mark.asyncio
    async def test_test_generation_thresholds(self, evaluator):
        """Test generation has higher thresholds."""
        result = await evaluator.execute(
            operation_type="test_generation",
            duration_sec=45,  # Under 60s threshold
            memory_mb=400,  # Under 500MB threshold
        )

        assert result.ok

    @pytest.mark.asyncio
    async def test_query_stricter_thresholds(self, evaluator):
        """Query operations have stricter thresholds."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=2,  # Over 1s threshold
        )

        assert not result.ok

    @pytest.mark.asyncio
    async def test_default_thresholds_used(self, evaluator):
        """Unknown operation types use default thresholds."""
        result = await evaluator.execute(
            operation_type="unknown_operation", duration_sec=25
        )

        # Default threshold is 30s, so should pass
        assert result.ok


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class TestPerformanceScore:
    """Test performance score calculation."""

    @pytest.mark.asyncio
    async def test_perfect_score_no_issues(self, evaluator):
        """Operations within all thresholds get perfect score."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=0.5,
            memory_mb=20,
            io_operations=5,
        )

        assert result.data["performance_score"] == 1.0

    @pytest.mark.asyncio
    async def test_score_decreases_with_violations(self, evaluator):
        """Exceeding thresholds decreases score."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=2.0,  # Exceeds 1s
            memory_mb=100,  # Exceeds 50MB
        )

        assert result.data["performance_score"] < 1.0

    @pytest.mark.asyncio
    async def test_confidence_matches_score(self, evaluator):
        """Component confidence should match performance score."""
        result = await evaluator.execute(operation_type="query", duration_sec=0.8)

        assert result.confidence == result.data["performance_score"]


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class TestBottleneckIdentification:
    """Test bottleneck detection."""

    @pytest.mark.asyncio
    async def test_identifies_time_bottleneck(self, evaluator):
        """Should identify time as bottleneck."""
        result = await evaluator.execute(operation_type="query", duration_sec=2.0)

        assert "time" in result.data["bottlenecks"]

    @pytest.mark.asyncio
    async def test_identifies_memory_bottleneck(self, evaluator):
        """Should identify memory as bottleneck."""
        result = await evaluator.execute(operation_type="query", memory_mb=100)

        assert "memory" in result.data["bottlenecks"]

    @pytest.mark.asyncio
    async def test_identifies_multiple_bottlenecks(self, evaluator):
        """Should identify all bottlenecks."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=2.0,
            memory_mb=100,
            io_operations=50,
        )

        assert "time" in result.data["bottlenecks"]
        assert "memory" in result.data["bottlenecks"]
        assert "io" in result.data["bottlenecks"]


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class TestOptimizationSuggestions:
    """Test optimization suggestion generation."""

    @pytest.mark.asyncio
    async def test_provides_time_suggestions(self, evaluator):
        """Should provide time optimization suggestions."""
        result = await evaluator.execute(
            operation_type="test_generation", duration_sec=70
        )

        assert len(result.data["suggestions"]) > 0
        assert any("test" in s.lower() for s in result.data["suggestions"])

    @pytest.mark.asyncio
    async def test_provides_memory_suggestions(self, evaluator):
        """Should provide memory optimization suggestions."""
        result = await evaluator.execute(operation_type="sync", memory_mb=300)

        assert any(
            "memory" in s.lower() or "batch" in s.lower()
            for s in result.data["suggestions"]
        )

    @pytest.mark.asyncio
    async def test_provides_io_suggestions(self, evaluator):
        """Should provide I/O optimization suggestions."""
        result = await evaluator.execute(operation_type="sync", io_operations=10000)

        assert any(
            "i/o" in s.lower() or "bulk" in s.lower() or "batch" in s.lower()
            for s in result.data["suggestions"]
        )


# ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
class TestSeverityLevels:
    """Test issue severity classification."""

    @pytest.mark.asyncio
    async def test_moderate_overhead_warning(self, evaluator):
        """Moderate overhead should be warning."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=1.3,  # 30% over threshold
        )

        duration_issue = next(
            i for i in result.data["issues"] if i["type"] == "duration"
        )
        assert duration_issue["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_high_overhead_error(self, evaluator):
        """High overhead should be error."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=2.0,  # 100% over threshold
        )

        duration_issue = next(
            i for i in result.data["issues"] if i["type"] == "duration"
        )
        assert duration_issue["severity"] == "error"


# ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class TestMetadata:
    """Test result metadata completeness."""

    @pytest.mark.asyncio
    async def test_includes_bottleneck_flags(self, evaluator):
        """Metadata should include bottleneck flags."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=2.0,
            memory_mb=100,
        )

        assert result.metadata["has_time_issues"] is True
        assert result.metadata["has_memory_issues"] is True

    @pytest.mark.asyncio
    async def test_includes_operation_type(self, evaluator):
        """Metadata should include operation type."""
        result = await evaluator.execute(
            operation_type="test_generation", duration_sec=30
        )

        assert result.metadata["operation_type"] == "test_generation"

    @pytest.mark.asyncio
    async def test_suggests_optimization_handler(self, evaluator):
        """Should suggest optimization_handler when issues exist."""
        result = await evaluator.execute(operation_type="query", duration_sec=2.0)

        assert result.next_suggested == "optimization_handler"

    @pytest.mark.asyncio
    async def test_tracks_duration(self, evaluator):
        """Should track evaluation duration."""
        result = await evaluator.execute(operation_type="query", duration_sec=0.5)

        assert result.duration_sec >= 0.0


# ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_no_metrics_perfect_score(self, evaluator):
        """No metrics provided should result in perfect score."""
        result = await evaluator.execute(operation_type="query")

        assert result.ok
        assert result.data["performance_score"] == 1.0

    @pytest.mark.asyncio
    async def test_partial_metrics_evaluated(self, evaluator):
        """Should evaluate only provided metrics."""
        result = await evaluator.execute(
            operation_type="query",
            duration_sec=0.5,
            # No memory or I/O metrics
        )

        assert result.ok
        # Only duration should be in metrics
        assert "duration_sec" in result.data["metrics"]
