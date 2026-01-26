# src/will/phases/sandbox_validation_phase.py

"""
Sandbox Validation Phase - Validates generated tests in isolation.

Runs generated tests using PytestSandboxRunner to verify they execute correctly
before promoting them to the main test suite.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from features.test_generation.sandbox import PytestSandboxRunner
from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult


if TYPE_CHECKING:
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7g8h-9i0j-1k2l3m4n5o6p
# ID: d7fae2fd-a786-42f3-8969-21307c12fcbb
class SandboxValidationPhase:
    """
    Validates generated tests by running them in an isolated sandbox.

    This phase ensures tests are syntactically correct and executable
    before they're promoted to the main test suite.
    """

    def __init__(self, context):
        self.context = context
        self.file_handler = FileHandler()
        self.sandbox = PytestSandboxRunner(
            file_handler=self.file_handler, repo_root=str(settings.REPO_PATH)
        )

    # ID: b2c3d4e5-f6g7-8h9i-0j1k-2l3m4n5o6p7q
    # ID: 3902df50-3fc5-4b54-971c-3f3b7f36ce8c
    async def execute(self, ctx: WorkflowContext) -> PhaseResult:
        """
        Execute sandbox validation on generated tests.

        Args:
            ctx: Workflow context containing generated test code

        Returns:
            PhaseResult with validation results
        """
        start_time = time.time()

        # Get generated test code from context
        generated_tests = ctx.data.get("generated_tests", [])

        if not generated_tests:
            logger.info("No tests to validate")
            return PhaseResult(
                name="sandbox_validation",
                ok=True,
                data={"skipped": True, "reason": "no tests generated"},
                duration_sec=time.time() - start_time,
            )

        passed_count = 0
        failed_count = 0
        results = []

        for test_item in generated_tests:
            test_code = test_item.get("code", "")
            symbol_name = test_item.get("symbol_name", "unknown")

            if not test_code:
                continue

            logger.info("🧪 Validating test for: %s", symbol_name)

            # Run in sandbox
            sandbox_result = await self.sandbox.run(
                code=test_code, symbol_name=symbol_name, timeout_seconds=30
            )

            if sandbox_result.passed:
                passed_count += 1
                logger.info("✅ Test passed: %s", symbol_name)
            else:
                failed_count += 1
                logger.warning(
                    "❌ Test failed: %s - %s", symbol_name, sandbox_result.error
                )

            results.append(
                {
                    "symbol_name": symbol_name,
                    "passed": sandbox_result.passed,
                    "error": sandbox_result.error,
                    "passed_tests": sandbox_result.passed_tests,
                    "failed_tests": sandbox_result.failed_tests,
                }
            )

        duration = time.time() - start_time

        logger.info(
            "🏁 Sandbox validation complete: %d passed, %d failed",
            passed_count,
            failed_count,
        )

        return PhaseResult(
            name="sandbox_validation",
            ok=True,  # Phase succeeds even if some tests fail
            data={
                "total_tests": len(generated_tests),
                "passed": passed_count,
                "failed": failed_count,
                "results": results,
            },
            duration_sec=duration,
        )
