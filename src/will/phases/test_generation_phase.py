# src/will/phases/test_generation_phase.py
# ID: will.phases.test_generation_phase

"""
Test Generation Phase Implementation

Generates tests for new or modified code to improve coverage.
Only used in coverage_remediation and full_feature_development workflows.

Constitutional Principle: Tests validate behavior and increase coverage
Generated tests are validated in sandbox before promotion.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 3273338d-c5af-420e-a706-3b06411ccb76
class TestGenerationPhase:
    """
    Test generation phase - creates tests for coverage improvement.

    This phase is used in:
    - coverage_remediation workflow (generate missing tests)
    - full_feature_development workflow (test new features)

    This phase is SKIPPED in:
    - refactor_modularity workflow (uses existing tests only)
    """

    def __init__(self, core_context: CoreContext):
        self.context = core_context
        self.tracer = DecisionTracer()

    # ID: 283a42db-c4b9-4bed-b9a8-36ed4a95c7ab
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute test generation phase"""
        start = time.time()

        try:
            # Check if this workflow needs test generation
            workflow_type = context.workflow_type

            if workflow_type == "refactor_modularity":
                logger.info("⭐️ Skipping test generation (refactor workflow)")
                return PhaseResult(
                    name="test_generation",
                    ok=True,
                    data={
                        "skipped": True,
                        "reason": "Not applicable to refactor workflow",
                    },
                    duration_sec=time.time() - start,
                )

            # Get files that need tests
            code_gen_data = context.results.get("code_generation", {}).get("data", {})
            detailed_plan = code_gen_data.get("detailed_plan")

            if not detailed_plan:
                logger.info("No code generated, skipping test generation")
                return PhaseResult(
                    name="test_generation",
                    ok=True,
                    data={"skipped": True, "reason": "no_code_generated"},
                    duration_sec=time.time() - start,
                )

            # Extract files that need tests
            target_files = self._extract_target_files(detailed_plan)

            if not target_files:
                logger.info("No files require test generation")
                return PhaseResult(
                    name="test_generation",
                    ok=True,
                    data={"skipped": True, "reason": "no_targets"},
                    duration_sec=time.time() - start,
                )

            logger.info("🧪 Generating tests for %d files...", len(target_files))

            # TODO: Integrate with EnhancedTestGenerator
            # For now, this is a stub that acknowledges the need
            # but doesn't actually generate tests

            logger.warning("⚠️ Test generation not yet implemented - placeholder phase")
            logger.info("Files needing tests: %s", ", ".join(target_files))

            duration = time.time() - start

            # Trace decision
            self.tracer.record(
                agent="TestGenerationPhase",
                decision_type="test_planning",
                rationale=f"Identified {len(target_files)} files requiring test coverage",
                chosen_action="test_generation_stub",
                context={
                    "target_files": target_files,
                    "workflow": workflow_type,
                },
                confidence=0.5,  # Low confidence since not implemented
            )

            return PhaseResult(
                name="test_generation",
                ok=True,
                data={
                    "tests_generated": 0,
                    "target_files": target_files,
                    "note": "Test generation stub - actual implementation pending",
                },
                duration_sec=duration,
            )

        except Exception as e:
            logger.error("Test generation error: %s", e, exc_info=True)
            duration = time.time() - start

            return PhaseResult(
                name="test_generation",
                ok=False,
                error=str(e),
                duration_sec=duration,
            )

    def _extract_target_files(self, detailed_plan: dict) -> list[str]:
        """
        Extract files that need test coverage.

        Strategy:
        - New files always need tests
        - Modified files may need additional tests
        - Look for production code (src/*), not test code
        """
        target_files = []

        steps = detailed_plan.get("steps", [])
        for step in steps:
            params = step.get("params", {})
            file_path = params.get("file_path", "")

            # Only production code needs tests
            if file_path.startswith("src/") and not file_path.startswith("src/tests/"):
                target_files.append(file_path)

        return target_files
