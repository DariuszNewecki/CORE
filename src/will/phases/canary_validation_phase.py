# src/will/phases/canary_validation_phase.py

"""
Canary Validation Phase Implementation

Runs existing tests against new code to verify behavioral preservation.

Constitutional Principle: WORKING CODE > MISSING TESTS
- Canary acts as ADVISORY SENSOR during refactoring
- Test failures are REPORTED but don't BLOCK progress
- Refactoring changes APIs → old tests fail (expected)
- Generate new tests AFTER refactoring via coverage_remediation workflow

UNIX Philosophy: One tool, one job
- This tool's job: Run tests and report results
- NOT: Block refactoring on expected API changes
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import DetailedPlan, PhaseResult
from will.orchestration.decision_tracer import DecisionTracer

from .canary.pytest_runner import PytestRunner
from .canary.result_builder import CanaryResultBuilder
from .canary.test_discovery import TestDiscoveryService


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 81269e6a-2a4b-4966-931c-3af061fc2407
class CanaryValidationPhase:
    """
    Canary validation phase - runs existing tests in ADVISORY mode.

    This phase reports test results but does NOT block refactoring.
    Rationale: Refactoring changes APIs → tests expect old structure.

    Job: Detect and report. Human decides what to do with failures.
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self.tracer = DecisionTracer()
        self.test_discovery = TestDiscoveryService()
        self.pytest_runner = PytestRunner()
        self.result_builder = CanaryResultBuilder()

    # ID: c94fbab8-42b8-4880-b990-d7d77e78c15a
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute canary validation phase in advisory mode"""
        start = time.time()

        try:
            # Get files affected by code generation
            code_gen_data = context.results.get("code_generation", {})
            detailed_plan = code_gen_data.get("detailed_plan")

            if not detailed_plan:
                logger.info("No code changes to validate")
                return self.result_builder.build_skipped_result(
                    "no_code_changes", time.time() - start
                )

            # Determine which test files to run
            affected_files = self._extract_affected_files(detailed_plan)
            test_paths = self.test_discovery.find_related_tests(affected_files)

            if not test_paths:
                return self.result_builder.build_no_tests_result(time.time() - start)

            logger.info(
                "🕯️ Running canary tests for %d test files (ADVISORY MODE)...",
                len(test_paths),
            )

            # Run pytest on relevant test files
            test_result = await self.pytest_runner.run_tests(test_paths)
            duration = time.time() - start

            # Trace decision
            self._trace_test_execution(test_paths, test_result)

            # Build appropriate result based on test outcome
            if test_result["exit_code"] == 0:
                return self.result_builder.build_success_result(
                    test_result, test_paths, duration
                )
            else:
                return self.result_builder.build_advisory_failure_result(
                    test_result, test_paths, duration
                )

        except Exception as e:
            duration = time.time() - start
            return self.result_builder.build_error_result(e, duration)

    def _extract_affected_files(self, detailed_plan: DetailedPlan) -> list[str]:
        """Extract file paths from detailed plan."""
        affected = []

        for step in detailed_plan.steps:
            file_path = step.params.get("file_path")
            if file_path:
                affected.append(file_path)

        return affected

    def _trace_test_execution(self, test_paths: list[str], result: dict) -> None:
        """Record decision trace for test execution."""
        self.tracer.record(
            agent="CanaryValidationPhase",
            decision_type="test_execution",
            rationale=f"Ran {len(test_paths)} test files in advisory mode",
            chosen_action="pytest_existing_tests_advisory",
            context={
                "tests_run": len(test_paths),
                "passed": result["passed"],
                "failed": result["failed"],
                "exit_code": result["exit_code"],
                "advisory_mode": True,
            },
            confidence=1.0 if result["exit_code"] == 0 else 0.5,
        )
