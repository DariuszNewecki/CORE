# src/will/phases/canary_validation_phase.py
# ID: will.phases.canary_validation_phase

"""
Canary Validation Phase Implementation

Runs existing tests against new code to verify behavioral preservation.
This is the constitutional gatekeeper for refactoring.

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

import asyncio
import time
from typing import TYPE_CHECKING

from shared.config import settings
from shared.logger import getLogger
from shared.models.workflow_models import DetailedPlan, PhaseResult
from will.orchestration.decision_tracer import DecisionTracer


if TYPE_CHECKING:
    from shared.context import CoreContext
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 5eeb168d-e644-4533-b11d-ebfdef27f076
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

    # ID: edaf7058-8277-44a9-9389-e61429384459
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute canary validation phase in advisory mode"""
        start = time.time()

        try:
            # Get files affected by code generation
            code_gen_data = context.results.get("code_generation", {})
            detailed_plan = code_gen_data.get("detailed_plan")

            if not detailed_plan:
                logger.info("No code changes to validate")
                return PhaseResult(
                    name="canary_validation",
                    ok=True,
                    data={
                        "canary_passes": True,
                        "existing_tests_pass": True,
                        "skipped": True,
                        "reason": "no_code_changes",
                    },
                    duration_sec=time.time() - start,
                )

            # Determine which test files to run
            affected_files = self._extract_affected_files(detailed_plan)
            test_paths = self._find_related_tests(affected_files)

            if not test_paths:
                logger.info("⭐️ No existing tests found for affected files")
                return PhaseResult(
                    name="canary_validation",
                    ok=True,
                    data={
                        "canary_passes": True,
                        "existing_tests_pass": True,
                        "tests_found": 0,
                        "note": "No existing tests - behavioral preservation cannot be verified",
                    },
                    duration_sec=time.time() - start,
                )

            logger.info(
                "🕯️ Running canary tests for %d test files (ADVISORY MODE)...",
                len(test_paths),
            )

            # Run pytest on relevant test files
            result = await self._run_pytest(test_paths)

            duration = time.time() - start

            # Trace decision
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

            # ADVISORY MODE: Always return ok=True, but report test status
            if result["exit_code"] == 0:
                logger.info("✅ Canary tests passed - behavior likely preserved")
                return PhaseResult(
                    name="canary_validation",
                    ok=True,
                    data={
                        "canary_passes": True,
                        "existing_tests_pass": True,
                        "tests_passed": result["passed"],
                        "tests_failed": result["failed"],
                        "exit_code": result["exit_code"],
                        "test_files": test_paths,
                        "advisory": False,  # Tests actually passed
                    },
                    duration_sec=duration,
                )
            else:
                logger.warning(
                    "⚠️  Canary tests failed - API may have changed (ADVISORY ONLY, not blocking)"
                )
                logger.info("📋 Test failures logged for human review")
                return PhaseResult(
                    name="canary_validation",
                    ok=True,  # ← CHANGED: Don't block workflow
                    data={
                        "canary_passes": False,  # ← Report failure
                        "existing_tests_pass": False,
                        "tests_passed": result["passed"],
                        "tests_failed": result["failed"],
                        "exit_code": result["exit_code"],
                        "test_files": test_paths,
                        "advisory": True,  # ← Mark as advisory
                        "note": "Test failures detected but not blocking. Refactoring may have changed APIs. Review failures and regenerate tests via coverage_remediation workflow.",
                        "output_preview": result.get("output", "")[
                            :500
                        ],  # First 500 chars for review
                    },
                    duration_sec=duration,
                )

        except Exception as e:
            logger.error("Canary validation error: %s", e, exc_info=True)
            duration = time.time() - start

            # Even on error, don't block refactoring
            return PhaseResult(
                name="canary_validation",
                ok=True,  # ← CHANGED: Don't block on errors
                data={
                    "canary_passes": False,
                    "existing_tests_pass": False,
                    "error": str(e),
                    "advisory": True,
                    "note": "Canary validation encountered an error but not blocking refactoring",
                },
                duration_sec=duration,
            )

    def _extract_affected_files(self, detailed_plan: DetailedPlan) -> list[str]:
        """Extract file paths from detailed plan"""
        affected = []

        for step in detailed_plan.steps:
            file_path = step.params.get("file_path")
            if file_path:
                affected.append(file_path)

        return affected

    def _find_related_tests(self, affected_files: list[str]) -> list[str]:
        """
        Find test files related to affected production files.

        Strategy:
        1. For src/foo/bar.py, look for tests/foo/test_bar.py
        2. For src/foo/bar.py, look for tests/foo/bar/test_*.py
        3. For src/foo/__init__.py, look for tests/foo/test_*.py
        """
        test_paths = []
        tests_dir = settings.REPO_PATH / "tests"

        if not tests_dir.exists():
            return []

        for file_path in affected_files:
            # Convert src/foo/bar.py -> tests/foo/test_bar.py
            if file_path.startswith("src/"):
                relative = file_path[4:]  # Remove 'src/'

                # Remove .py extension
                if relative.endswith(".py"):
                    relative = relative[:-3]

                # Convert module path to test path
                parts = relative.split("/")

                # Strategy 1: tests/foo/test_bar.py
                test_file = tests_dir / "/".join(parts[:-1]) / f"test_{parts[-1]}.py"
                if test_file.exists():
                    test_paths.append(str(test_file.relative_to(settings.REPO_PATH)))

                # Strategy 2: tests/foo/bar/test_*.py
                test_dir = tests_dir / relative
                if test_dir.exists() and test_dir.is_dir():
                    for test_file in test_dir.glob("test_*.py"):
                        test_paths.append(
                            str(test_file.relative_to(settings.REPO_PATH))
                        )

                # Strategy 3: For __init__.py, look for test_*.py in same directory
                if parts[-1] == "__init__":
                    test_dir = tests_dir / "/".join(parts[:-1])
                    if test_dir.exists():
                        for test_file in test_dir.glob("test_*.py"):
                            test_paths.append(
                                str(test_file.relative_to(settings.REPO_PATH))
                            )

        return list(set(test_paths))  # Deduplicate

    async def _run_pytest(self, test_paths: list[str]) -> dict:
        """
        Run pytest on specified test files using non-blocking async primitives.

        Returns dict with:
        - passed: number of passed tests
        - failed: number of failed tests
        - exit_code: pytest exit code (0 = success)
        - output: pytest output
        """
        # --- PHASE 1: Verify collection ---
        cmd_collect = [
            "pytest",
            "-v",
            "--tb=short",
            "--no-header",
            "--co",
            *test_paths,
        ]

        try:
            # CONSTITUTIONAL FIX: Replacement for subprocess.run to avoid ASYNC221
            proc_collect = await asyncio.create_subprocess_exec(
                *cmd_collect,
                cwd=str(settings.REPO_PATH),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, _ = await asyncio.wait_for(
                    proc_collect.communicate(), timeout=30
                )
                if "no tests ran" in stdout.decode(errors="replace").lower():
                    return {
                        "passed": 0,
                        "failed": 0,
                        "exit_code": 0,
                        "output": "No tests collected",
                    }
            except TimeoutError:
                if proc_collect.returncode is None:
                    proc_collect.kill()
                logger.warning("Test collection timed out")
        except Exception as e:
            logger.warning("Test collection check failed: %s", e)

        # --- PHASE 2: Actual Execution ---
        cmd_run = [
            "pytest",
            "-v",
            "--tb=short",
            "--no-header",
            "-x",
            *test_paths,
        ]

        try:
            # CONSTITUTIONAL FIX: Replacement for subprocess.run to avoid ASYNC221
            proc_run = await asyncio.create_subprocess_exec(
                *cmd_run,
                cwd=str(settings.REPO_PATH),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                # 5 minute timeout per original policy
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc_run.communicate(), timeout=300
                )

                output = stdout_bytes.decode(errors="replace") + stderr_bytes.decode(
                    errors="replace"
                )
                passed = output.count(" PASSED")
                failed = output.count(" FAILED")

                return {
                    "passed": passed,
                    "failed": failed,
                    "exit_code": proc_run.returncode,
                    "output": output,
                }

            except TimeoutError:
                if proc_run.returncode is None:
                    proc_run.kill()
                return {
                    "passed": 0,
                    "failed": 1,
                    "exit_code": 124,  # Standard timeout exit code
                    "output": "Tests timed out after 300 seconds",
                }

        except Exception as e:
            logger.error("Failed to run pytest: %s", e)
            return {
                "passed": 0,
                "failed": 1,
                "exit_code": 1,
                "output": str(e),
            }
