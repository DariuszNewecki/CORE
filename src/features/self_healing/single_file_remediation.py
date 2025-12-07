# src/features/self_healing/single_file_remediation.py

"""
Enhanced single-file test generation with comprehensive context analysis.

This version uses the EnhancedTestGenerator which gathers deep context
before generating tests, preventing misunderstandings and improving quality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.self_healing.coverage_analyzer import CoverageAnalyzer
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from src.features.self_healing.test_generator import EnhancedTestGenerator
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 0c2cfe25-2da0-4aaa-8927-f1312c7a3825
class EnhancedSingleFileRemediationService:
    """
    Generates tests for a single file using comprehensive context analysis.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        file_path: Path,
        max_complexity: str = "SIMPLE",
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.target_file = file_path
        self.analyzer = CoverageAnalyzer()
        self.generator = EnhancedTestGenerator(
            cognitive_service,
            auditor_context,
            use_iterative_fixing=False,
            max_complexity=max_complexity,
        )

    # ID: 840acb0f-7ec4-4f61-bc69-62c9b2fda26d
    async def remediate(self) -> dict[str, Any]:
        """
        Generate comprehensive tests for the target file.
        """
        logger.info("Enhanced Single-File Test Generation: %s", self.target_file)

        # Make the path relative to repo root if needed
        if str(self.target_file).startswith(str(settings.REPO_PATH)):
            relative_path = self.target_file.relative_to(settings.REPO_PATH)
        else:
            relative_path = self.target_file

        target_str = str(relative_path)

        # Derive module part (strip leading 'src/' if present)
        if "src/" in target_str:
            module_part = target_str.split("src/", 1)[1]
        else:
            module_part = target_str

        module_name = module_part.replace("/", ".").replace(".py", "")
        module_parts = module_name.split(".")

        # Compute test file path
        if len(module_parts) > 1:
            test_dir = Path("tests") / module_parts[0]
        else:
            test_dir = Path("tests")
        test_filename = f"test_{Path(module_part).stem}.py"
        test_file = test_dir / test_filename

        goal = self._build_goal_description(module_name)

        logger.debug("Target: %s | Test: %s", module_name, test_file)

        # --- Test generation + validation ------------------------------------
        try:
            logger.info("Generating tests with enhanced context...")

            result = await self.generator.generate_test(
                module_path=str(relative_path),
                test_file=str(test_file),
                goal=goal,
                target_coverage=75.0,
            )

        except Exception as exc:
            logger.error(
                "Unexpected error during enhanced single-file remediation for %s: %s",
                self.target_file,
                exc,
                exc_info=True,
            )
            return {
                "status": "error",
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "error": str(exc),
            }

        # Defensive: ensure result is a dict
        if not isinstance(result, dict):
            msg = (
                f"Generator returned unexpected result type: {type(result)!r}. "
                "Expected a dict."
            )
            logger.error(msg)
            return {
                "status": "error",
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "error": msg,
            }

        status = result.get("status")
        error_details = result.get("error")
        violations = result.get("violations") or []
        test_result = result.get("test_result") or {}

        # --- Happy path -------------------------------------------------------
        if status == "success":
            final_coverage = self._measure_final_coverage(str(relative_path))
            logger.info(
                "Test generation succeeded for %s. Final coverage: %s%%",
                self.target_file,
                final_coverage,
            )

            # Log context usage details for audit trail
            coverage_from_context = (
                result.get("context_used", {}).get("coverage")
                if isinstance(result.get("context_used"), dict)
                else None
            )
            uncovered_functions = (
                result.get("context_used", {}).get("uncovered_functions", 0)
                if isinstance(result.get("context_used"), dict)
                else 0
            )

            if coverage_from_context is not None:
                logger.debug(
                    "Context stats: coverage=%.1f%%, uncovered_funcs=%d",
                    coverage_from_context,
                    uncovered_functions,
                )

            return {
                "status": "completed",
                "succeeded": 1,
                "failed": 0,
                "total": 1,
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "final_coverage": final_coverage,
                "raw_result": result,
            }

        # --- Partial success: tests created but some fail ----------------------
        if status == "tests_created_with_failures":
            execution_result = result.get("execution_result", {})
            logger.warning(
                "Tests generated for %s but some failed execution", self.target_file
            )

            return {
                "status": "partial_success",
                "succeeded": 0,
                "failed": 0,
                "total": 1,
                "file": str(self.target_file),
                "module": module_name,
                "test_file": str(test_file),
                "execution_result": execution_result,
            }

        # --- Error path -----------------------------------------------------
        if not error_details:
            if status:
                error_details = f"Test generation failed with status '{status}'."
            else:
                error_details = "Test generation failed for unknown reasons."

        logger.error(
            "Test generation failed for %s: %s", self.target_file, error_details
        )

        if violations:
            for v in violations:
                if isinstance(v, dict):
                    logger.warning(
                        "Violation: [%s] %s: %s",
                        v.get("severity", "info"),
                        v.get("rule", "unknown"),
                        v.get("message", ""),
                    )

        return {
            "status": "failed",
            "file": str(self.target_file),
            "module": module_name,
            "test_file": str(test_file),
            "error": error_details,
            "violations": violations,
            "test_result": test_result,
            "raw_result": result,
        }

    def _build_goal_description(self, module_name: str) -> str:
        return (
            f"Create comprehensive unit tests for {module_name}. "
            "Focus on testing core functionality, edge cases, and error handling. "
            "Use appropriate mocks for external dependencies. "
            "Target 75%+ coverage with clear, maintainable tests."
        )

    def _measure_final_coverage(self, module_rel_path: str) -> float | None:
        try:
            coverage_data = self.analyzer.get_module_coverage()
            if not coverage_data:
                return None
            return coverage_data.get(module_rel_path)
        except Exception as exc:
            logger.debug(
                "Could not measure final coverage for %s: %s",
                module_rel_path,
                exc,
            )
            return None
