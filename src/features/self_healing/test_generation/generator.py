# src/features/self_healing/test_generation/generator.py

"""
Main orchestration for EnhancedTestGenerator.

This is the conductor - coordinates generation, repair, execution, and fixing.
"""

from __future__ import annotations

from typing import Any

from features.self_healing.complexity_filter import ComplexityFilter
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from .automatic_repair import AutomaticRepairService
from .executor import TestExecutor
from .generation_workflow import GenerationWorkflow
from .llm_correction import LLMCorrectionService
from .repair_workflow import RepairWorkflow
from .single_test_fixer import SingleTestFixer, TestFailureParser
from .test_scorer import TestScorer
from .test_validator import TestValidator


logger = getLogger(__name__)


# ID: 672b54f9-4eb0-4faf-baa4-8d3f3656f8e9
class EnhancedTestGenerator:
    """
    High-level orchestrator for test generation with self-correction.

    Strategy:
    1. Generate tests via LLM
    2. Apply automatic repairs (deterministic fixes)
    3. If needed, use LLM correction
    4. Execute tests and fix individual failures
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        use_iterative_fixing: bool = True,
        max_fix_attempts: int = 3,
        max_complexity: str = "MODERATE",
    ):
        auto_repair = AutomaticRepairService()
        complexity_filter = ComplexityFilter(max_complexity=max_complexity)

        self.generation = GenerationWorkflow(
            cognitive_service, complexity_filter, auto_repair, max_complexity
        )
        self.validator = TestValidator(auditor_context)
        self.repair = RepairWorkflow(
            auto_repair,
            LLMCorrectionService(cognitive_service, auditor_context),
            self.validator,
            max_fix_attempts,
        )
        self.executor = TestExecutor()
        self.test_fixer = SingleTestFixer(cognitive_service, max_attempts=3)
        self.failure_parser = TestFailureParser()
        self.scorer = TestScorer()
        self.use_iterative_fixing = use_iterative_fixing

    # ID: 04ccde33-fbfa-481e-8b53-b6f9df07c80f
    async def generate_test(
        self, module_path: str, test_file: str, goal: str, target_coverage: float
    ) -> dict[str, Any]:
        """Main entry point for enhanced test generation with self-correction."""
        logger.info("Starting enhanced test generation for %s", module_path)

        # Check complexity
        if not await self.generation.check_complexity(module_path):
            return {"status": "skipped", "reason": "complexity_filter"}

        # Build context and generate code
        module_context = await self.generation.build_context(module_path)
        code = await self.generation.generate_initial_code(
            module_context, goal, target_coverage
        )
        if not code:
            return {"status": "failed", "error": "no_valid_code_generated"}

        # Repair code if needed
        repair_result = await self.repair.repair_code(
            test_file, code, module_context, goal
        )
        if repair_result["status"] != "success":
            return {
                "status": "failed",
                "error": "validation_failed_after_repairs",
                "details": repair_result.get("message"),
                "violations": repair_result.get("violations", []),
            }

        # Execute tests
        current_code = repair_result["code"]
        execution_result = await self.executor.execute_test(
            test_file=test_file, code=current_code
        )

        if execution_result.get("status") == "success":
            logger.info("✅ Tests generated and all passed!")
            return execution_result

        if execution_result.get("status") == "failed":
            return await self._handle_test_failures(
                test_file, module_path, module_context, execution_result
            )

        return execution_result

    async def _handle_test_failures(
        self, test_file: str, module_path: str, module_context, execution_result: dict
    ) -> dict[str, Any]:
        """Handle and attempt to fix failing tests."""
        logger.warning("Tests generated but some failed when executed")

        output = execution_result.get("output", "")
        initial_passed = self.scorer.count_passed(output)
        initial_total = self.scorer.count_total(output)
        initial_score = self.scorer.format_score(initial_passed, initial_total)

        logger.info("Initial results: %s", initial_score)

        failures = self.failure_parser.parse_failures(output)
        if not failures or len(failures) > 10:
            return {
                "status": "tests_created_with_failures",
                "test_file": test_file,
                "execution_result": execution_result,
                "message": "Tests were successfully generated but had runtime failures",
                "initial_score": initial_score,
            }

        # Attempt to fix individual failures
        fixed_count = await self._fix_individual_tests(
            test_file, module_path, module_context, failures
        )

        if fixed_count == 0:
            return {
                "status": "tests_created_with_failures",
                "test_file": test_file,
                "execution_result": execution_result,
                "message": "Could not fix any failing tests",
                "initial_score": initial_score,
            }

        # Re-run tests after fixes
        return await self._rerun_after_fixes(
            test_file, fixed_count, initial_passed, initial_total, initial_score
        )

    async def _fix_individual_tests(
        self, test_file: str, module_path: str, module_context, failures: list
    ) -> int:
        """Fix individual failing tests and return count of successful fixes."""
        logger.info("Attempting to fix %s failing tests individually...", len(failures))

        fixed_count = 0
        for failure in failures:
            fix_result = await self.test_fixer.fix_test(
                test_file=settings.REPO_PATH / test_file,
                test_name=failure["test_name"],
                failure_info=failure,
                source_file=(
                    settings.REPO_PATH / module_path if module_context else None
                ),
            )
            if fix_result.get("status") == "fixed":
                fixed_count += 1
                logger.info("✅ Fixed %s", failure["test_name"])
            else:
                logger.warning("❌ Could not fix %s", failure["test_name"])

        return fixed_count

    async def _rerun_after_fixes(
        self,
        test_file: str,
        fixed_count: int,
        initial_passed: int,
        initial_total: int,
        initial_score: str,
    ) -> dict[str, Any]:
        """Re-run tests after fixes and return results."""
        logger.info("Re-running tests after fixing %s tests...", fixed_count)

        test_file_path = settings.REPO_PATH / test_file
        try:
            modified_code = test_file_path.read_text()
            import ast

            ast.parse(modified_code)
        except Exception as e:
            logger.error("Test file corrupted after fixes: %s", e)
            return {
                "status": "tests_created_with_failures",
                "test_file": test_file,
                "message": f"Fixed {fixed_count} tests but file became corrupted",
                "initial_score": initial_score,
            }

        final_result = await self.executor.execute_test(
            test_file=test_file, code=modified_code
        )
        final_output = final_result.get("output", "")
        final_passed = self.scorer.count_passed(final_output)
        final_total = self.scorer.count_total(final_output)
        final_score = self.scorer.format_score(final_passed, final_total)
        improvement = final_passed - initial_passed

        if final_result.get("status") == "success":
            logger.info("🎉 All tests now pass! (%s)", final_score)
            logger.info(
                "Fixed %s tests, improved by %s passing tests", fixed_count, improvement
            )
            return {
                "status": "success",
                "message": f"All tests pass (fixed {fixed_count} individual test failures)",
                "tests_fixed": fixed_count,
                "initial_score": initial_score,
                "final_score": final_score,
            }

        logger.info("Final results: %s (Improvement: +%s)", final_score, improvement)
        return {
            "status": "tests_created_with_failures",
            "test_file": test_file,
            "execution_result": final_result,
            "message": f"Tests generated, fixed {fixed_count} failures, but some still fail",
            "tests_fixed": fixed_count,
            "initial_score": initial_score,
            "final_score": final_score,
        }
