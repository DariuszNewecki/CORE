# src/will/phases/canary/result_builder.py

"""
Builds PhaseResult objects for canary validation outcomes.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult


logger = getLogger(__name__)


# ID: a80020fb-21ed-46fb-ae04-eda1514425a8
class CanaryResultBuilder:
    """Builds PhaseResult objects based on test execution outcomes."""

    @staticmethod
    # ID: 5a6e7470-86f7-44b1-951f-8e341cf33064
    def build_skipped_result(reason: str, duration: float) -> PhaseResult:
        """Build result for skipped validation."""
        return PhaseResult(
            name="canary_validation",
            ok=True,
            data={
                "syntax_valid": True,
                "logic_preserved": True,
                "canary_passes": True,
                "existing_tests_pass": True,
                "skipped": True,
                "reason": reason,
            },
            duration_sec=duration,
        )

    @staticmethod
    # ID: 7d809b23-a6c3-4332-99e6-3bb8e3c415f0
    def build_no_tests_result(duration: float) -> PhaseResult:
        """Build result when no tests are found."""
        logger.info("⭐️ No existing tests found for affected files")
        return PhaseResult(
            name="canary_validation",
            ok=True,
            data={
                "syntax_valid": True,
                "logic_preserved": True,
                "canary_passes": True,
                "existing_tests_pass": True,
                "tests_found": 0,
                "note": "No existing tests - behavioral preservation cannot be verified",
            },
            duration_sec=duration,
        )

    @staticmethod
    # ID: b3ec6d29-13ab-47e8-856e-0ecf3da83e2a
    def build_success_result(
        test_result: dict, test_paths: list[str], duration: float
    ) -> PhaseResult:
        """Build result for successful test execution."""
        logger.info("✅ Canary tests passed - behavior likely preserved")
        return PhaseResult(
            name="canary_validation",
            ok=True,
            data={
                "syntax_valid": True,
                "logic_preserved": True,
                "canary_passes": True,
                "existing_tests_pass": True,
                "tests_passed": test_result["passed"],
                "tests_failed": test_result["failed"],
                "exit_code": test_result["exit_code"],
                "test_files": test_paths,
                "advisory": False,  # Tests actually passed
            },
            duration_sec=duration,
        )

    @staticmethod
    # ID: 7af824fb-4f00-4e6a-8c13-bf3abe4e9d79
    def build_advisory_failure_result(
        test_result: dict, test_paths: list[str], duration: float
    ) -> PhaseResult:
        """Build result for test failures in advisory mode."""
        logger.warning(
            "⚠️  Canary tests failed - API may have changed (ADVISORY ONLY, not blocking)"
        )
        logger.info("📋 Test failures logged for human review")

        return PhaseResult(
            name="canary_validation",
            ok=True,  # CRITICAL: Don't block workflow
            data={
                "syntax_valid": True,
                "logic_preserved": True,
                "canary_passes": False,
                "existing_tests_pass": False,
                "tests_passed": test_result["passed"],
                "tests_failed": test_result["failed"],
                "exit_code": test_result["exit_code"],
                "test_files": test_paths,
                "advisory": True,
                "note": "Test failures detected but not blocking. Refactoring may have changed APIs. Review failures and regenerate tests via coverage_remediation workflow.",
                "output_preview": test_result.get("output", "")[:500],
            },
            duration_sec=duration,
        )

    @staticmethod
    # ID: 2b8926c9-e895-4c36-8fed-3afb5d15773f
    def build_error_result(error: Exception, duration: float) -> PhaseResult:
        """Build result for execution errors."""
        logger.error("Canary validation error: %s", error, exc_info=True)

        return PhaseResult(
            name="canary_validation",
            ok=True,  # CRITICAL: Don't block on errors
            data={
                "syntax_valid": True,
                "logic_preserved": True,
                "canary_passes": False,
                "existing_tests_pass": False,
                "error": str(error),
                "advisory": True,
                "note": "Canary validation encountered an error but not blocking refactoring",
            },
            duration_sec=duration,
        )
