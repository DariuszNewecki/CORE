# src/body/evaluators/performance_evaluator.py

"""
PerformanceEvaluator - Assesses performance metrics and identifies bottlenecks.

Constitutional Alignment:
- Phase: AUDIT (Quality assessment and pattern detection)
- Authority: POLICY (Enforces performance requirements)
- Purpose: Evaluate whether operations meet performance thresholds
- Boundary: Read-only analysis, no mutations

This component EVALUATES performance, does not OPTIMIZE it.
Optimization happens in subsequent phases based on evaluation results.

Performance Dimensions:
1. **Time**: Execution duration, response latency
2. **Memory**: Memory usage, allocation patterns
3. **I/O**: File operations, database queries, network calls
4. **Complexity**: Algorithm complexity, resource scaling

Usage:
    evaluator = PerformanceEvaluator()
    result = await evaluator.execute(
        duration_sec=1.5,
        memory_mb=250,
        operation_type="test_generation"
    )

    if not result.ok:
        print(f"Performance issues: {result.data['issues']}")
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from body.evaluators.base_evaluator import BaseEvaluator
from shared.component_primitive import ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 5faaa14c-b0d8-4f43-b968-333ae4ccd2ff
class PerformanceEvaluator(BaseEvaluator):
    """
    Evaluates performance metrics against operational thresholds.

    Thresholds (by operation type):
    - test_generation: <60s, <500MB
    - refactor: <30s, <300MB
    - sync: <120s, <200MB
    - validation: <5s, <100MB
    - query: <1s, <50MB

    Output provides:
    - Binary performance status (ok: True/False)
    - List of performance issues
    - Performance score (0.0-1.0)
    - Bottleneck identification
    - Optimization suggestions
    """

    # Performance threshold definitions
    THRESHOLDS: ClassVar[dict[str, dict[str, int]]] = {
        "test_generation": {
            "max_duration_sec": 60,
            "max_memory_mb": 500,
            "max_io_operations": 1000,
        },
        "refactor": {
            "max_duration_sec": 30,
            "max_memory_mb": 300,
            "max_io_operations": 500,
        },
        "sync": {
            "max_duration_sec": 120,
            "max_memory_mb": 200,
            "max_io_operations": 5000,
        },
        "validation": {
            "max_duration_sec": 5,
            "max_memory_mb": 100,
            "max_io_operations": 100,
        },
        "query": {
            "max_duration_sec": 1,
            "max_memory_mb": 50,
            "max_io_operations": 10,
        },
        "default": {
            "max_duration_sec": 30,
            "max_memory_mb": 200,
            "max_io_operations": 500,
        },
    }

    # ID: 8789c64d-2e2c-465d-947b-cb2899bc80b6
    async def execute(
        self,
        operation_type: str = "default",
        duration_sec: float | None = None,
        memory_mb: float | None = None,
        io_operations: int | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Evaluate performance metrics against thresholds.

        Args:
            operation_type: Type of operation (for threshold selection)
            duration_sec: Execution duration in seconds
            memory_mb: Memory usage in megabytes
            io_operations: Number of I/O operations (file/db/network)
            **kwargs: Additional metrics (cpu_percent, cache_hits, etc.)

        Returns:
            ComponentResult with performance assessment
        """
        start_time = time.time()

        # Get thresholds for operation type
        thresholds = self.THRESHOLDS.get(operation_type, self.THRESHOLDS["default"])

        # Collect metrics
        metrics = {
            "duration_sec": duration_sec,
            "memory_mb": memory_mb,
            "io_operations": io_operations,
        }

        # Add additional metrics from kwargs
        for key in ["cpu_percent", "cache_hits", "cache_misses", "db_queries"]:
            if key in kwargs:
                metrics[key] = kwargs[key]

        # Evaluate each metric against thresholds
        issues = []
        bottlenecks = []
        suggestions = []

        if duration_sec is not None:
            issue = self._check_duration(
                duration_sec, thresholds["max_duration_sec"], operation_type
            )
            if issue:
                issues.append(issue)
                bottlenecks.append("time")
                suggestions.append(self._suggest_time_optimization(operation_type))

        if memory_mb is not None:
            issue = self._check_memory(
                memory_mb, thresholds["max_memory_mb"], operation_type
            )
            if issue:
                issues.append(issue)
                bottlenecks.append("memory")
                suggestions.append(self._suggest_memory_optimization(operation_type))

        if io_operations is not None:
            issue = self._check_io(
                io_operations, thresholds["max_io_operations"], operation_type
            )
            if issue:
                issues.append(issue)
                bottlenecks.append("io")
                suggestions.append(self._suggest_io_optimization(operation_type))

        # Calculate performance score
        performance_score = self._calculate_score(metrics, thresholds)

        # Determine if performance is acceptable
        ok = len(issues) == 0

        logger.info(
            "PerformanceEvaluator: %s (score: %.2f, %d issues)",
            "PASS" if ok else "FAIL",
            performance_score,
            len(issues),
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=ok,
            phase=self.phase,
            data={
                "issues": issues,
                "performance_score": performance_score,
                "bottlenecks": bottlenecks,
                "suggestions": suggestions,
                "metrics": metrics,
                "thresholds": thresholds,
            },
            confidence=performance_score,
            next_suggested="optimization_handler" if issues else None,
            metadata={
                "operation_type": operation_type,
                "has_time_issues": "time" in bottlenecks,
                "has_memory_issues": "memory" in bottlenecks,
                "has_io_issues": "io" in bottlenecks,
            },
            duration_sec=time.time() - start_time,
        )

    # ID: 2ff5f335-df35-4074-b404-bc3ee8d855dc
    def _check_duration(
        self, actual: float, threshold: float, operation_type: str
    ) -> dict[str, Any] | None:
        """Check if duration exceeds threshold."""
        if actual > threshold:
            overhead_pct = ((actual - threshold) / threshold) * 100
            return {
                "type": "duration",
                "severity": "error" if overhead_pct > 50 else "warning",
                "message": f"Operation took {actual:.2f}s (threshold: {threshold}s, +{overhead_pct:.0f}%)",
                "actual": actual,
                "threshold": threshold,
                "overhead_percent": overhead_pct,
            }
        return None

    # ID: 60d599f5-1689-46c7-b6c3-edade0115b58
    def _check_memory(
        self, actual: float, threshold: float, operation_type: str
    ) -> dict[str, Any] | None:
        """Check if memory usage exceeds threshold."""
        if actual > threshold:
            overhead_pct = ((actual - threshold) / threshold) * 100
            return {
                "type": "memory",
                "severity": "error" if overhead_pct > 50 else "warning",
                "message": f"Memory usage {actual:.0f}MB (threshold: {threshold}MB, +{overhead_pct:.0f}%)",
                "actual": actual,
                "threshold": threshold,
                "overhead_percent": overhead_pct,
            }
        return None

    # ID: 91756d65-7e4f-4794-8542-a6b653646caa
    def _check_io(
        self, actual: int, threshold: int, operation_type: str
    ) -> dict[str, Any] | None:
        """Check if I/O operations exceed threshold."""
        if actual > threshold:
            overhead_pct = ((actual - threshold) / threshold) * 100
            return {
                "type": "io",
                "severity": "error" if overhead_pct > 100 else "warning",
                "message": f"I/O operations: {actual} (threshold: {threshold}, +{overhead_pct:.0f}%)",
                "actual": actual,
                "threshold": threshold,
                "overhead_percent": overhead_pct,
            }
        return None

    # ID: 7beb51dc-7e5d-4b04-9436-53932b83d42c
    def _calculate_score(
        self, metrics: dict[str, Any], thresholds: dict[str, Any]
    ) -> float:
        """
        Calculate overall performance score (0.0-1.0).

        Score is weighted average of metric/threshold ratios.
        Lower ratio is better (staying under threshold = 1.0 score).
        """
        scores = []
        weights = []

        if metrics.get("duration_sec") is not None:
            ratio = metrics["duration_sec"] / thresholds["max_duration_sec"]
            # If within threshold (ratio <= 1.0), score = 1.0
            # If over threshold, score decreases proportionally
            scores.append(min(1.0, 1.0 / ratio) if ratio > 0 else 1.0)
            weights.append(0.4)  # Time is most important

        if metrics.get("memory_mb") is not None:
            ratio = metrics["memory_mb"] / thresholds["max_memory_mb"]
            scores.append(min(1.0, 1.0 / ratio) if ratio > 0 else 1.0)
            weights.append(0.3)

        if metrics.get("io_operations") is not None:
            ratio = metrics["io_operations"] / thresholds["max_io_operations"]
            scores.append(min(1.0, 1.0 / ratio) if ratio > 0 else 1.0)
            weights.append(0.3)

        if not scores:
            return 1.0  # No metrics provided = perfect score

        # Weighted average
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
        return round(weighted_score, 2)

    # ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
    def _suggest_time_optimization(self, operation_type: str) -> str:
        """Suggest time optimization strategies."""
        suggestions = {
            "test_generation": "Consider reducing test complexity or using batch generation",
            "refactor": "Profile code to identify slow operations; consider incremental refactoring",
            "sync": "Enable parallel sync operations or reduce sync scope",
            "validation": "Cache validation results or reduce validation scope",
            "query": "Add database indexes or optimize query patterns",
            "default": "Profile operation to identify bottlenecks",
        }
        return suggestions.get(operation_type, suggestions["default"])

    # ID: f51da377-3ea7-47dd-a06b-4b8f8479c180
    def _suggest_memory_optimization(self, operation_type: str) -> str:
        """Suggest memory optimization strategies."""
        suggestions = {
            "test_generation": "Process files in smaller batches or use streaming",
            "refactor": "Process code in chunks rather than loading entire file",
            "sync": "Process in batches; use pagination for large datasets",
            "validation": "Release memory after each validation",
            "query": "Use generators instead of loading all results",
            "default": "Reduce data held in memory; use lazy loading",
        }
        return suggestions.get(operation_type, suggestions["default"])

    # ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
    def _suggest_io_optimization(self, operation_type: str) -> str:
        """Suggest I/O optimization strategies."""
        suggestions = {
            "test_generation": "Reduce file writes; combine multiple operations",
            "refactor": "Batch file operations; use in-memory buffers",
            "sync": "Use bulk database operations instead of individual inserts",
            "validation": "Cache frequently accessed files",
            "query": "Enable query result caching",
            "default": "Batch I/O operations; reduce redundant reads/writes",
        }
        return suggestions.get(operation_type, suggestions["default"])
