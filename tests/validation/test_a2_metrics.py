# tests/validation/a2_metrics.py
"""
Metrics collection for A2 capability validation.

This module tracks success rates, failure modes, and performance characteristics
for Phase 0 validation tasks. It determines whether CORE should proceed to
Phase 1 (semantic infrastructure) based on objective thresholds.

Constitutional Principle: reason_with_purpose
- Metrics drive architectural decisions
- Objective thresholds prevent bias
- Comprehensive data enables post-analysis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from shared.logger import getLogger

logger = getLogger(__name__)


class FailureMode(Enum):
    """
    Categories of generation failures.

    Used to analyze WHY tasks fail, which informs:
    - Whether semantic infrastructure will help
    - What alternative approaches might work
    - Where to focus optimization efforts
    """

    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    CONSTITUTIONAL_VIOLATION = "constitutional_violation"
    SEMANTIC_MISPLACEMENT = "semantic_misplacement"
    MISSING_DOCSTRING = "missing_docstring"
    MISSING_TYPE_HINTS = "missing_type_hints"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"
    LLM_REFUSAL = "llm_refusal"
    CONTEXT_OVERFLOW = "context_overflow"
    UNKNOWN = "unknown"


@dataclass
class TaskResult:
    """
    Result of a single validation task.

    Captures all metrics needed to evaluate constitutional compliance,
    semantic placement, and execution success.
    """

    # Task identification
    task_id: str
    goal: str
    difficulty: str  # "simple" | "medium" | "complex"

    # Success metrics (primary evaluation criteria)
    constitutional_compliance: bool
    semantic_placement_score: float  # 0.0-1.0
    execution_success: bool
    has_tests: bool

    # Performance metrics
    generation_time_seconds: float
    context_tokens: int
    generation_tokens: int

    # Quality metrics (contributes to constitutional compliance)
    has_docstring: bool
    has_type_hints: bool
    passes_formatting: bool

    # Failure analysis
    failure_mode: FailureMode | None = None
    failure_details: str | None = None

    # Generated artifacts (for manual review)
    generated_code: str = ""
    actual_location: str | None = None

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)

    def is_successful(self) -> bool:
        """
        Determine if task was successful overall.

        Success = constitutional compliance AND execution success.
        Semantic placement is tracked separately as it's subjective.
        """
        return self.constitutional_compliance and self.execution_success

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "difficulty": self.difficulty,
            "successful": self.is_successful(),
            "constitutional_compliance": self.constitutional_compliance,
            "semantic_placement_score": self.semantic_placement_score,
            "execution_success": self.execution_success,
            "has_tests": self.has_tests,
            "generation_time_seconds": self.generation_time_seconds,
            "context_tokens": self.context_tokens,
            "generation_tokens": self.generation_tokens,
            "has_docstring": self.has_docstring,
            "has_type_hints": self.has_type_hints,
            "passes_formatting": self.passes_formatting,
            "failure_mode": self.failure_mode.value if self.failure_mode else None,
            "failure_details": self.failure_details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ValidationReport:
    """
    Aggregate report for all validation tasks.

    Determines go/no-go decision for Phase 1 based on:
    - Constitutional compliance rate (≥70%)
    - Semantic placement accuracy (≥80%)
    - Execution success rate (≥50%)
    """

    # Summary counts
    total_tasks: int
    successful_tasks: int

    # Success rates by category (PRIMARY DECISION CRITERIA)
    constitutional_compliance_rate: float
    semantic_placement_accuracy: float
    execution_success_rate: float
    test_coverage_rate: float

    # Performance statistics
    mean_generation_time: float
    std_generation_time: float
    mean_context_tokens: int
    mean_generation_tokens: int

    # Success by difficulty (diagnostic)
    simple_success_rate: float
    medium_success_rate: float
    complex_success_rate: float

    # Failure analysis
    failure_modes: dict[FailureMode, int]

    # Individual results (for detailed analysis)
    task_results: list[TaskResult]

    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)

    def passes_threshold(self) -> bool:
        """
        Check if results meet Phase 0 success threshold.

        Thresholds (from roadmap):
        - Constitutional compliance: ≥70%
        - Semantic placement: ≥80%
        - Execution success: ≥50%

        All three must pass to proceed to Phase 1.
        """
        return (
            self.constitutional_compliance_rate >= 0.70
            and self.semantic_placement_accuracy >= 0.80
            and self.execution_success_rate >= 0.50
        )

    def get_recommendation(self) -> str:
        """
        Generate recommendation based on results.

        Returns:
            "PROCEED" - Move to Phase 1
            "REFINE" - Fix issues and retry Phase 0
            "PIVOT" - Core capability not validated, change approach
        """
        if self.passes_threshold():
            return "PROCEED"

        # Check which thresholds failed
        compliance_ok = self.constitutional_compliance_rate >= 0.70
        placement_ok = self.semantic_placement_accuracy >= 0.80
        execution_ok = self.execution_success_rate >= 0.50

        # If close to threshold, recommend refinement
        if (
            self.constitutional_compliance_rate >= 0.60
            and self.semantic_placement_accuracy >= 0.70
            and self.execution_success_rate >= 0.40
        ):
            return "REFINE"

        # If far from threshold, recommend pivot
        return "PIVOT"

    def to_markdown(self) -> str:
        """
        Generate comprehensive markdown report.

        Used for:
        - Phase 0 decision document
        - Academic paper metrics
        - Team review and discussion
        """
        recommendation = self.get_recommendation()
        status_icon = (
            "✅"
            if recommendation == "PROCEED"
            else "⚠️"
            if recommendation == "REFINE"
            else "❌"
        )

        md = f"""# Phase 0 Validation Report

**Status**: {status_icon} {recommendation}
**Generated**: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}

---

## Executive Summary

Phase 0 validates whether LLMs can generate constitutionally-compliant code
using existing CORE infrastructure (no semantic enhancements).

**Results**:
- **Total Tasks**: {self.total_tasks}
- **Successful Tasks**: {self.successful_tasks} ({self.successful_tasks/self.total_tasks*100:.1f}%)
- **Recommendation**: **{recommendation}**

---

## Success Metrics

| Metric | Result | Threshold | Status |
|--------|--------|-----------|--------|
| **Constitutional Compliance** | {self.constitutional_compliance_rate*100:.1f}% | ≥70% | {'✅ PASS' if self.constitutional_compliance_rate >= 0.70 else '❌ FAIL'} |
| **Semantic Placement** | {self.semantic_placement_accuracy*100:.1f}% | ≥80% | {'✅ PASS' if self.semantic_placement_accuracy >= 0.80 else '❌ FAIL'} |
| **Execution Success** | {self.execution_success_rate*100:.1f}% | ≥50% | {'✅ PASS' if self.execution_success_rate >= 0.50 else '❌ FAIL'} |
| Test Coverage | {self.test_coverage_rate*100:.1f}% | N/A | ℹ️ INFO |

### Threshold Analysis

"""

        # Add specific analysis for each metric
        if self.constitutional_compliance_rate < 0.70:
            gap = (0.70 - self.constitutional_compliance_rate) * 100
            md += f"""
**Constitutional Compliance: {self.constitutional_compliance_rate*100:.1f}% (need 70%)**
- Gap: {gap:.1f} percentage points
- Issue: LLMs struggling with docstrings, type hints, or syntax
- Implication: This is an LLM quality/prompting issue, not context issue
- Semantic infrastructure unlikely to fix this significantly
"""

        if self.semantic_placement_accuracy < 0.80:
            gap = (0.80 - self.semantic_placement_accuracy) * 100
            md += f"""
**Semantic Placement: {self.semantic_placement_accuracy*100:.1f}% (need 80%)**
- Gap: {gap:.1f} percentage points
- Issue: Code placed in wrong modules/layers
- Implication: Could benefit from semantic infrastructure (anchors, module context)
- Phase 1 directly addresses this
"""

        if self.execution_success_rate < 0.50:
            gap = (0.50 - self.execution_success_rate) * 100
            md += f"""
**Execution Success: {self.execution_success_rate*100:.1f}% (need 50%)**
- Gap: {gap:.1f} percentage points
- Issue: Generated code has runtime errors
- Implication: Major implementation issues, may need prompt refinement
- Semantic infrastructure won't fix runtime errors
"""

        md += f"""

---

## Performance Statistics

- **Mean Generation Time**: {self.mean_generation_time:.2f}s (±{self.std_generation_time:.2f}s)
- **Mean Context Size**: {self.mean_context_tokens:,} tokens
- **Mean Generation Size**: {self.mean_generation_tokens:,} tokens

### Time Analysis
"""

        if self.mean_generation_time < 5.0:
            md += "- ✅ Generation is fast (< 5s average)\n"
        elif self.mean_generation_time < 10.0:
            md += "- ⚠️ Generation is moderate (5-10s average)\n"
        else:
            md += "- ❌ Generation is slow (> 10s average)\n"

        md += f"""

---

## Success by Difficulty

| Difficulty | Success Rate | Expected | Status |
|------------|--------------|----------|--------|
| **Simple** | {self.simple_success_rate*100:.1f}% | ~90% | {'✅' if self.simple_success_rate >= 0.80 else '❌'} |
| **Medium** | {self.medium_success_rate*100:.1f}% | ~70% | {'✅' if self.medium_success_rate >= 0.60 else '❌'} |
| **Complex** | {self.complex_success_rate*100:.1f}% | ~50% | {'✅' if self.complex_success_rate >= 0.40 else '❌'} |

### Difficulty Analysis
"""

        # Analyze if difficulty pattern makes sense
        if self.simple_success_rate < self.medium_success_rate:
            md += "- ⚠️ Unexpected: Medium tasks more successful than simple tasks\n"
        if self.medium_success_rate < self.complex_success_rate:
            md += "- ⚠️ Unexpected: Complex tasks more successful than medium tasks\n"

        if (
            self.simple_success_rate
            > self.medium_success_rate
            > self.complex_success_rate
        ):
            md += "- ✅ Expected pattern: Success rate decreases with difficulty\n"

        md += """

---

## Failure Mode Analysis

"""

        if not self.failure_modes:
            md += "No failures detected! All tasks passed.\n"
        else:
            md += "| Failure Mode | Count | % of Total |\n"
            md += "|--------------|-------|------------|\n"

            total_failures = sum(self.failure_modes.values())
            for mode, count in sorted(self.failure_modes.items(), key=lambda x: -x[1]):
                if count > 0:
                    pct = (count / self.total_tasks) * 100
                    md += f"| {mode.value.replace('_', ' ').title()} | {count} | {pct:.1f}% |\n"

            md += "\n### Failure Mode Insights\n\n"

            # Provide specific insights for common failure modes
            if FailureMode.MISSING_DOCSTRING in self.failure_modes:
                count = self.failure_modes[FailureMode.MISSING_DOCSTRING]
                md += f"- **Missing Docstrings ({count})**: Prompt should emphasize docstring requirement more\n"

            if FailureMode.MISSING_TYPE_HINTS in self.failure_modes:
                count = self.failure_modes[FailureMode.MISSING_TYPE_HINTS]
                md += f"- **Missing Type Hints ({count})**: Prompt should include type hint examples\n"

            if FailureMode.SYNTAX_ERROR in self.failure_modes:
                count = self.failure_modes[FailureMode.SYNTAX_ERROR]
                md += f"- **Syntax Errors ({count})**: LLM quality issue, consider different model or temperature\n"

            if FailureMode.SEMANTIC_MISPLACEMENT in self.failure_modes:
                count = self.failure_modes[FailureMode.SEMANTIC_MISPLACEMENT]
                md += f"- **Semantic Misplacement ({count})**: Phase 1 (architectural anchors) should fix this\n"

            if FailureMode.IMPORT_ERROR in self.failure_modes:
                count = self.failure_modes[FailureMode.IMPORT_ERROR]
                md += f"- **Import Errors ({count})**: Need better context about available modules\n"

        md += "\n---\n\n## Individual Task Results\n\n"

        # Group by difficulty for readability
        for difficulty in ["simple", "medium", "complex"]:
            difficulty_tasks = [
                r for r in self.task_results if r.difficulty == difficulty
            ]
            if not difficulty_tasks:
                continue

            md += f"### {difficulty.title()} Tasks\n\n"

            for result in difficulty_tasks:
                status_icon = "✅" if result.is_successful() else "❌"
                md += f"#### {status_icon} {result.task_id}\n\n"
                md += f"**Goal**: {result.goal}\n\n"
                md += "**Metrics**:\n"
                md += f"- Constitutional Compliance: {'✅' if result.constitutional_compliance else '❌'}\n"
                md += f"- Semantic Placement: {result.semantic_placement_score:.2f}\n"
                md += f"- Execution Success: {'✅' if result.execution_success else '❌'}\n"
                md += f"- Generation Time: {result.generation_time_seconds:.2f}s\n"
                md += f"- Docstring: {'✅' if result.has_docstring else '❌'}\n"
                md += f"- Type Hints: {'✅' if result.has_type_hints else '❌'}\n"

                if result.failure_mode:
                    md += f"\n**Failure Mode**: {result.failure_mode.value}\n"
                    if result.failure_details:
                        md += f"**Details**: {result.failure_details}\n"

                md += "\n"

        md += "---\n\n## Recommendation\n\n"

        if recommendation == "PROCEED":
            md += f"""### ✅ PROCEED TO PHASE 1

**Rationale**:
- Constitutional compliance at {self.constitutional_compliance_rate*100:.1f}% (≥70% required)
- Semantic placement at {self.semantic_placement_accuracy*100:.1f}% (≥80% required)
- Execution success at {self.execution_success_rate*100:.1f}% (≥50% required)

**Expected Impact of Phase 1**:
Phase 1 (semantic infrastructure) should improve:
- Semantic placement: {self.semantic_placement_accuracy*100:.1f}% → 95%+ (architectural anchors)
- Constitutional compliance: {self.constitutional_compliance_rate*100:.1f}% → 85%+ (policy context)
- Execution success: {self.execution_success_rate*100:.1f}% → 70%+ (better context)

**Next Steps**:
1. Document these baseline results
2. Begin Phase 1 implementation (policy vectorization)
3. Re-run validation suite after Phase 1
4. Measure improvement quantitatively
"""

        elif recommendation == "REFINE":
            md += """### ⚠️ REFINE BEFORE PROCEEDING

**Rationale**:
Results are close to threshold but not quite there. Small improvements
could push us over the line.

**Issues Identified**:
"""
            if self.constitutional_compliance_rate < 0.70:
                md += f"- Constitutional compliance at {self.constitutional_compliance_rate*100:.1f}% (need 70%)\n"
            if self.semantic_placement_accuracy < 0.80:
                md += f"- Semantic placement at {self.semantic_placement_accuracy*100:.1f}% (need 80%)\n"
            if self.execution_success_rate < 0.50:
                md += f"- Execution success at {self.execution_success_rate*100:.1f}% (need 50%)\n"

            md += """
**Recommended Actions**:
1. Analyze top failure modes (see Failure Mode Analysis above)
2. Refine generation prompts to address common issues
3. Re-run Phase 0 validation
4. If still failing, consider pivot options

**Time Investment**: 2-3 days for prompt refinement
"""

        else:  # PIVOT
            md += """### ❌ PIVOT RECOMMENDED

**Rationale**:
Results are significantly below threshold. Proceeding to Phase 1 is unlikely
to close the gap, as the issues are fundamental rather than context-related.

**Critical Issues**:
"""
            if self.constitutional_compliance_rate < 0.50:
                md += f"- Constitutional compliance at {self.constitutional_compliance_rate*100:.1f}% (critical)\n"
                md += "  → LLM cannot reliably produce compliant code\n"
            if self.execution_success_rate < 0.30:
                md += f"- Execution success at {self.execution_success_rate*100:.1f}% (critical)\n"
                md += "  → Generated code has fundamental errors\n"

            md += """
**Pivot Options**:

1. **Hybrid Approach**
   - LLM generates code
   - Human reviews and approves before commit
   - Still autonomous, but with safety net

2. **Narrow Scope**
   - Only generate tests, not production code
   - Tests are lower risk, easier to validate
   - Build confidence before expanding scope

3. **Research Mode**
   - Document why A2 is hard
   - Publish findings about LLM limitations
   - Academic contribution without full A2

**Recommended Next Step**:
Conduct failure analysis workshop to determine root causes and select pivot option.
"""

        md += "\n---\n\n## Appendix: Raw Data\n\n"
        md += "```json\n"
        md += "{\n"
        md += f'  "total_tasks": {self.total_tasks},\n'
        md += f'  "successful_tasks": {self.successful_tasks},\n'
        md += f'  "constitutional_compliance_rate": {self.constitutional_compliance_rate},\n'
        md += f'  "semantic_placement_accuracy": {self.semantic_placement_accuracy},\n'
        md += f'  "execution_success_rate": {self.execution_success_rate}\n'
        md += "}\n"
        md += "```\n"

        return md

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "constitutional_compliance_rate": self.constitutional_compliance_rate,
            "semantic_placement_accuracy": self.semantic_placement_accuracy,
            "execution_success_rate": self.execution_success_rate,
            "test_coverage_rate": self.test_coverage_rate,
            "mean_generation_time": self.mean_generation_time,
            "std_generation_time": self.std_generation_time,
            "mean_context_tokens": self.mean_context_tokens,
            "mean_generation_tokens": self.mean_generation_tokens,
            "simple_success_rate": self.simple_success_rate,
            "medium_success_rate": self.medium_success_rate,
            "complex_success_rate": self.complex_success_rate,
            "failure_modes": {k.value: v for k, v in self.failure_modes.items()},
            "passes_threshold": self.passes_threshold(),
            "recommendation": self.get_recommendation(),
            "generated_at": self.generated_at.isoformat(),
        }


class MetricsCollector:
    """
    Collects and aggregates validation metrics.

    Usage:
        collector = MetricsCollector()

        for task in tasks:
            result = run_task(task)
            collector.add_result(result)

        report = collector.generate_report()
        print(report.to_markdown())
    """

    def __init__(self):
        self.results: list[TaskResult] = []

    def add_result(self, result: TaskResult) -> None:
        """
        Add a task result to the collection.

        Logs immediate feedback for monitoring progress.
        """
        self.results.append(result)

        status = "✅" if result.is_successful() else "❌"
        logger.info(
            f"{status} Task {result.task_id} completed: "
            f"compliant={result.constitutional_compliance}, "
            f"placement={result.semantic_placement_score:.2f}, "
            f"executes={result.execution_success}, "
            f"time={result.generation_time_seconds:.2f}s"
        )

    def generate_report(self) -> ValidationReport:
        """
        Generate aggregate validation report.

        Calculates all metrics and determines go/no-go decision.

        Raises:
            ValueError: If no results have been collected
        """
        if not self.results:
            raise ValueError(
                "No results to report. Add task results before generating report."
            )

        total = len(self.results)
        successful = sum(1 for r in self.results if r.is_successful())

        # Calculate success rates
        compliance_rate = (
            sum(1 for r in self.results if r.constitutional_compliance) / total
        )
        placement_rate = sum(r.semantic_placement_score for r in self.results) / total
        execution_rate = sum(1 for r in self.results if r.execution_success) / total
        test_rate = sum(1 for r in self.results if r.has_tests) / total

        # Performance statistics
        gen_times = [r.generation_time_seconds for r in self.results]
        mean_time = sum(gen_times) / len(gen_times)

        # Calculate standard deviation
        variance = sum((t - mean_time) ** 2 for t in gen_times) / len(gen_times)
        std_time = variance**0.5

        mean_ctx = sum(r.context_tokens for r in self.results) / total
        mean_gen = sum(r.generation_tokens for r in self.results) / total

        # Success by difficulty
        simple = [r for r in self.results if r.difficulty == "simple"]
        medium = [r for r in self.results if r.difficulty == "medium"]
        complex_tasks = [r for r in self.results if r.difficulty == "complex"]

        simple_rate = (
            sum(1 for r in simple if r.is_successful()) / len(simple) if simple else 0.0
        )
        medium_rate = (
            sum(1 for r in medium if r.is_successful()) / len(medium) if medium else 0.0
        )
        complex_rate = (
            sum(1 for r in complex_tasks if r.is_successful()) / len(complex_tasks)
            if complex_tasks
            else 0.0
        )

        # Failure mode analysis
        failure_modes: dict[FailureMode, int] = {}
        for result in self.results:
            if result.failure_mode:
                failure_modes[result.failure_mode] = (
                    failure_modes.get(result.failure_mode, 0) + 1
                )

        return ValidationReport(
            total_tasks=total,
            successful_tasks=successful,
            constitutional_compliance_rate=compliance_rate,
            semantic_placement_accuracy=placement_rate,
            execution_success_rate=execution_rate,
            test_coverage_rate=test_rate,
            mean_generation_time=mean_time,
            std_generation_time=std_time,
            mean_context_tokens=int(mean_ctx),
            mean_generation_tokens=int(mean_gen),
            simple_success_rate=simple_rate,
            medium_success_rate=medium_rate,
            complex_success_rate=complex_rate,
            failure_modes=failure_modes,
            task_results=self.results,
        )
