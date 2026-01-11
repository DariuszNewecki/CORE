"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/performance_evaluator.py
- Symbol: PerformanceEvaluator
- Status: 21 tests passed, some failed
- Passing tests: test_execute_with_all_metrics_within_thresholds, test_execute_with_duration_exceeded, test_execute_with_multiple_threshold_exceeded, test_execute_with_partial_metrics, test_execute_with_no_metrics, test_execute_with_additional_kwargs_metrics, test_execute_with_unknown_operation_type, test_check_duration_with_warning_severity, test_check_duration_with_error_severity, test_check_duration_within_threshold, test_check_memory_with_warning_severity, test_check_io_with_warning_severity, test_check_io_with_error_severity, test_calculate_score_with_all_metrics_within_thresholds, test_calculate_score_with_exceeded_thresholds, test_calculate_score_with_partial_metrics, test_suggest_time_optimization, test_suggest_memory_optimization, test_suggest_io_optimization, test_phase_property, test_execute_includes_duration
- Generated: 2026-01-11 03:21:37
"""

import pytest

from body.evaluators.performance_evaluator import PerformanceEvaluator


@pytest.mark.asyncio
async def test_execute_with_all_metrics_within_thresholds():
    """Test performance evaluation when all metrics are within thresholds."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="test_generation",
        duration_sec=30.0,
        memory_mb=250.0,
        io_operations=500,
    )
    assert result.ok
    assert result.data["issues"] == []
    assert result.data["performance_score"] == 1.0
    assert result.data["bottlenecks"] == []
    assert result.data["suggestions"] == []
    assert result.data["metrics"]["duration_sec"] == 30.0
    assert result.data["metrics"]["memory_mb"] == 250.0
    assert result.data["metrics"]["io_operations"] == 500
    assert result.confidence == 1.0
    assert result.next_suggested is None


@pytest.mark.asyncio
async def test_execute_with_duration_exceeded():
    """Test when duration exceeds threshold."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="validation", duration_sec=10.0, memory_mb=50.0, io_operations=50
    )
    assert not result.ok
    assert len(result.data["issues"]) == 1
    assert result.data["issues"][0]["type"] == "duration"
    assert result.data["issues"][0]["severity"] == "error"
    assert (
        "Operation took 10.00s (threshold: 5s, +100%)"
        in result.data["issues"][0]["message"]
    )
    assert result.data["bottlenecks"] == ["time"]
    assert len(result.data["suggestions"]) == 1
    assert result.data["performance_score"] < 1.0
    assert result.next_suggested == "optimization_handler"
    assert result.metadata["has_time_issues"]


@pytest.mark.asyncio
async def test_execute_with_multiple_threshold_exceeded():
    """Test when multiple metrics exceed thresholds."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="refactor", duration_sec=45.0, memory_mb=450.0, io_operations=600
    )
    assert not result.ok
    assert len(result.data["issues"]) == 3
    issue_types = {issue["type"] for issue in result.data["issues"]}
    assert issue_types == {"duration", "memory", "io"}
    assert set(result.data["bottlenecks"]) == {"time", "memory", "io"}
    assert len(result.data["suggestions"]) == 3
    assert result.metadata["has_time_issues"]
    assert result.metadata["has_memory_issues"]
    assert result.metadata["has_io_issues"]


@pytest.mark.asyncio
async def test_execute_with_partial_metrics():
    """Test when only some metrics are provided."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="test_generation",
        duration_sec=70.0,
        memory_mb=None,
        io_operations=None,
    )
    assert not result.ok
    assert len(result.data["issues"]) == 1
    assert result.data["issues"][0]["type"] == "duration"
    assert result.data["metrics"]["duration_sec"] == 70.0
    assert result.data["metrics"]["memory_mb"] is None
    assert result.data["metrics"]["io_operations"] is None
    assert result.data["performance_score"] < 1.0


@pytest.mark.asyncio
async def test_execute_with_no_metrics():
    """Test when no metrics are provided."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(operation_type="default")
    assert result.ok
    assert result.data["issues"] == []
    assert result.data["performance_score"] == 1.0
    assert result.data["bottlenecks"] == []
    assert result.data["suggestions"] == []


@pytest.mark.asyncio
async def test_execute_with_additional_kwargs_metrics():
    """Test with additional metrics provided via kwargs."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="validation",
        duration_sec=3.0,
        memory_mb=80.0,
        io_operations=50,
        cpu_percent=75.0,
        cache_hits=100,
        cache_misses=20,
        db_queries=15,
    )
    assert result.ok
    assert result.data["metrics"]["cpu_percent"] == 75.0
    assert result.data["metrics"]["cache_hits"] == 100
    assert result.data["metrics"]["cache_misses"] == 20
    assert result.data["metrics"]["db_queries"] == 15


@pytest.mark.asyncio
async def test_execute_with_unknown_operation_type():
    """Test with unknown operation type (should use default thresholds)."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="unknown_operation",
        duration_sec=40.0,
        memory_mb=250.0,
        io_operations=600,
    )
    assert not result.ok
    assert len(result.data["issues"]) == 3
    assert result.data["thresholds"] == evaluator.THRESHOLDS["default"]


@pytest.mark.asyncio
async def test_check_duration_with_warning_severity():
    """Test duration check with warning severity (overhead <= 50%)."""
    evaluator = PerformanceEvaluator()
    issue = evaluator._check_duration(45.0, 30.0, "refactor")
    assert issue is not None
    assert issue["type"] == "duration"
    assert issue["severity"] == "warning"
    assert issue["actual"] == 45.0
    assert issue["threshold"] == 30.0
    assert issue["overhead_percent"] == 50.0


@pytest.mark.asyncio
async def test_check_duration_with_error_severity():
    """Test duration check with error severity (overhead > 50%)."""
    evaluator = PerformanceEvaluator()
    issue = evaluator._check_duration(46.0, 30.0, "refactor")
    assert issue is not None
    assert issue["severity"] == "error"
    assert issue["overhead_percent"] > 50.0


@pytest.mark.asyncio
async def test_check_duration_within_threshold():
    """Test duration check when within threshold."""
    evaluator = PerformanceEvaluator()
    issue = evaluator._check_duration(25.0, 30.0, "refactor")
    assert issue is None


@pytest.mark.asyncio
async def test_check_memory_with_warning_severity():
    """Test memory check with warning severity (overhead <= 50%)."""
    evaluator = PerformanceEvaluator()
    issue = evaluator._check_memory(450.0, 300.0, "refactor")
    assert issue is not None
    assert issue["type"] == "memory"
    assert issue["severity"] == "warning"
    assert issue["actual"] == 450.0
    assert issue["threshold"] == 300.0


@pytest.mark.asyncio
async def test_check_io_with_warning_severity():
    """Test I/O check with warning severity (overhead <= 100%)."""
    evaluator = PerformanceEvaluator()
    issue = evaluator._check_io(750, 500, "refactor")
    assert issue is not None
    assert issue["type"] == "io"
    assert issue["severity"] == "warning"
    assert issue["overhead_percent"] == 50.0


@pytest.mark.asyncio
async def test_check_io_with_error_severity():
    """Test I/O check with error severity (overhead > 100%)."""
    evaluator = PerformanceEvaluator()
    issue = evaluator._check_io(1200, 500, "refactor")
    assert issue is not None
    assert issue["severity"] == "error"
    assert issue["overhead_percent"] > 100.0


@pytest.mark.asyncio
async def test_calculate_score_with_all_metrics_within_thresholds():
    """Test score calculation when all metrics are within thresholds."""
    evaluator = PerformanceEvaluator()
    metrics = {"duration_sec": 20.0, "memory_mb": 150.0, "io_operations": 200}
    thresholds = {
        "max_duration_sec": 30,
        "max_memory_mb": 300,
        "max_io_operations": 500,
    }
    score = evaluator._calculate_score(metrics, thresholds)
    assert score == 1.0


@pytest.mark.asyncio
async def test_calculate_score_with_exceeded_thresholds():
    """Test score calculation when metrics exceed thresholds."""
    evaluator = PerformanceEvaluator()
    metrics = {"duration_sec": 60.0, "memory_mb": 150.0, "io_operations": 750}
    thresholds = {
        "max_duration_sec": 30,
        "max_memory_mb": 300,
        "max_io_operations": 500,
    }
    score = evaluator._calculate_score(metrics, thresholds)
    assert score == 0.7


@pytest.mark.asyncio
async def test_calculate_score_with_partial_metrics():
    """Test score calculation with only some metrics provided."""
    evaluator = PerformanceEvaluator()
    metrics = {"duration_sec": 45.0, "memory_mb": None, "io_operations": None}
    thresholds = {
        "max_duration_sec": 30,
        "max_memory_mb": 300,
        "max_io_operations": 500,
    }
    score = evaluator._calculate_score(metrics, thresholds)
    assert score == 0.67


@pytest.mark.asyncio
async def test_suggest_time_optimization():
    """Test time optimization suggestions for different operation types."""
    evaluator = PerformanceEvaluator()
    suggestions = {
        "test_generation": evaluator._suggest_time_optimization("test_generation"),
        "refactor": evaluator._suggest_time_optimization("refactor"),
        "sync": evaluator._suggest_time_optimization("sync"),
        "validation": evaluator._suggest_time_optimization("validation"),
        "query": evaluator._suggest_time_optimization("query"),
        "unknown": evaluator._suggest_time_optimization("unknown"),
    }
    assert (
        suggestions["test_generation"]
        == "Consider reducing test complexity or using batch generation"
    )
    assert (
        suggestions["refactor"]
        == "Profile code to identify slow operations; consider incremental refactoring"
    )
    assert suggestions["sync"] == "Enable parallel sync operations or reduce sync scope"
    assert (
        suggestions["validation"]
        == "Cache validation results or reduce validation scope"
    )
    assert suggestions["query"] == "Add database indexes or optimize query patterns"
    assert suggestions["unknown"] == "Profile operation to identify bottlenecks"


@pytest.mark.asyncio
async def test_suggest_memory_optimization():
    """Test memory optimization suggestions for different operation types."""
    evaluator = PerformanceEvaluator()
    suggestion = evaluator._suggest_memory_optimization("refactor")
    assert suggestion == "Process code in chunks rather than loading entire file"


@pytest.mark.asyncio
async def test_suggest_io_optimization():
    """Test I/O optimization suggestions for different operation types."""
    evaluator = PerformanceEvaluator()
    suggestion = evaluator._suggest_io_optimization("sync")
    assert suggestion == "Use bulk database operations instead of individual inserts"


@pytest.mark.asyncio
async def test_phase_property():
    """Test that PerformanceEvaluator has correct phase."""
    evaluator = PerformanceEvaluator()
    from body.evaluators.performance_evaluator import ComponentPhase

    assert evaluator.phase == ComponentPhase.AUDIT


@pytest.mark.asyncio
async def test_execute_includes_duration():
    """Test that ComponentResult includes execution duration."""
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        operation_type="query", duration_sec=0.5, memory_mb=30.0
    )
    assert result.duration_sec >= 0.0
    assert isinstance(result.duration_sec, float)
