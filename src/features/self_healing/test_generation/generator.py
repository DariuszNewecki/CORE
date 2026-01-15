# src/features/self_healing/test_generation/generator.py

"""
Main orchestration for EnhancedTestGenerator.

This is the conductor - it coordinates the other components but doesn't
do the heavy lifting itself.
"""

from __future__ import annotations

import time
from typing import Any

from features.self_healing.complexity_filter import ComplexityFilter
from features.self_healing.test_context_analyzer import ModuleContext
from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.validation_pipeline import validate_code_async

from .automatic_repair import AutomaticRepairService
from .code_extractor import CodeExtractor
from .context_builder import ContextPackageBuilder
from .executor import TestExecutor
from .llm_correction import LLMCorrectionService

# from .prompt_builder import PromptBuilder
from .single_test_fixer import SingleTestFixer, TestFailureParser


logger = getLogger(__name__)


# ID: c29a04b7-8ecb-4aa5-a0bb-3823c6f969a1
class EnhancedTestGenerator:
    """
    High-level orchestrator for test generation with self-correction.

    Strategy:
    1. Generate tests via LLM
    2. Try automatic repairs (deterministic fixes)
    3. Only if needed, ask LLM to correct
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        use_iterative_fixing: bool = True,
        max_fix_attempts: int = 3,
        max_complexity: str = "MODERATE",
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.context_builder = ContextPackageBuilder()
        #        self.prompt_builder = PromptBuilder()
        self.code_extractor = CodeExtractor()
        self.executor = TestExecutor()
        self.complexity_filter = ComplexityFilter(max_complexity=max_complexity)
        self.auto_repair = AutomaticRepairService()
        self.llm_correction = LLMCorrectionService(cognitive_service, auditor_context)
        self.test_fixer = SingleTestFixer(cognitive_service, max_attempts=3)
        self.failure_parser = TestFailureParser()
        self.use_iterative_fixing = use_iterative_fixing
        self.max_fix_attempts = max_fix_attempts

    def _save_debug_artifact(self, name: str, content: str) -> None:
        """Save failed generation artifacts for inspection."""
        try:
            debug_dir = settings.REPO_PATH / "work" / "testing" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            filename = f"{name}_{timestamp}.txt"
            (debug_dir / filename).write_text(content, encoding="utf-8")
            logger.info("Saved debug artifact: %s", debug_dir / filename)
        except Exception as e:
            logger.warning("Failed to save debug artifact: %s", e)

    # ID: 8c2e6576-35ab-4940-96be-e0c0f08cfaed
    async def generate_test(
        self, module_path: str, test_file: str, goal: str, target_coverage: float
    ) -> dict[str, Any]:
        """
        Main entry point for enhanced test generation with self-correction.
        """
        logger.info("Starting enhanced test generation for %s", module_path)
        if not await self._check_complexity(module_path):
            return {"status": "skipped", "reason": "complexity_filter"}
        module_context: ModuleContext = await self.context_builder.build(module_path)
        code = await self._generate_initial_code(module_context, goal, target_coverage)
        if not code:
            return {"status": "failed", "error": "no_valid_code_generated"}
        code, initial_repairs = self.auto_repair.apply_all_repairs(code)
        if initial_repairs:
            logger.info("Applied initial repairs: %s", ", ".join(initial_repairs))
        current_code = code
        attempts = 0
        while attempts < self.max_fix_attempts:
            violations = await self._validate_code(
                test_file, current_code, module_context
            )
            if not violations:
                logger.info("✓ Test generation succeeded")
                break
            self._save_debug_artifact(f"failed_attempt_{attempts}", current_code)
            logger.info(
                "Validation failed (Attempt %s). Attempting repairs...", attempts + 1
            )
            repaired_code, repairs = self.auto_repair.apply_all_repairs(current_code)
            if repairs and repaired_code != current_code:
                logger.info("Applied automatic repairs: %s", ", ".join(repairs))
                current_code = repaired_code
                continue
            logger.warning(
                "After auto-repairs, still have %s violations:", len(violations)
            )
            for v in violations[:3]:
                logger.warning(
                    "  - %s: %s", v.get("rule", "unknown"), v.get("message", "")[:100]
                )
            attempts += 1
            logger.info("Automatic repairs insufficient, calling LLM for correction...")
            correction_result = await self.llm_correction.attempt_correction(
                file_path=test_file,
                code=current_code,
                violations=violations,
                module_context=module_context,
                goal=goal,
            )
            if correction_result["status"] == "success":
                current_code = correction_result["code"]
                current_code, post_repairs = self.auto_repair.apply_all_repairs(
                    current_code
                )
                if post_repairs:
                    logger.info(
                        "Applied post-correction repairs: %s", ", ".join(post_repairs)
                    )
            elif correction_result["status"] == "correction_failed_validation":
                failed_code = correction_result.get("code")
                failed_violations = correction_result.get("violations", [])
                if not failed_code:
                    logger.warning("LLM correction failed validation, no code returned")
                else:
                    logger.info(
                        "Applying automatic repairs to failed LLM correction..."
                    )
                    logger.info(
                        "LLM correction still has %s violations:",
                        len(failed_violations),
                    )
                    for v in failed_violations[:3]:
                        logger.info(
                            "  - %s: %s", v.get("rule"), v.get("message", "")[:100]
                        )
                    repaired, repairs = self.auto_repair.apply_all_repairs(failed_code)
                    if repairs and repaired != failed_code:
                        logger.info(
                            "Auto-repaired failed LLM code: %s", ", ".join(repairs)
                        )
                        current_code = repaired
                        continue
                if attempts >= self.max_fix_attempts:
                    return {
                        "status": "failed",
                        "error": "correction_failed_after_retries",
                        "details": correction_result.get("message"),
                        "violations": correction_result.get("violations", violations),
                    }
            else:
                logger.warning(
                    "LLM correction failed: %s", correction_result.get("message")
                )
                if attempts >= self.max_fix_attempts:
                    return {
                        "status": "failed",
                        "error": "correction_failed_after_retries",
                        "details": correction_result.get("message"),
                        "violations": violations,
                    }
        execution_result = await self.executor.execute_test(
            test_file=test_file, code=current_code
        )
        if execution_result.get("status") == "success":
            logger.info("✓ Tests generated and all passed!")
            return execution_result
        elif execution_result.get("status") == "failed":
            logger.warning("Tests generated but some failed when executed")
            output = execution_result.get("output", "")
            initial_passed = self._count_passed(output)
            initial_total = self._count_total(output)
            initial_rate = (
                initial_passed / initial_total * 100 if initial_total > 0 else 0
            )
            logger.info(
                "Initial results: %s/%s tests pass (%s%)",
                initial_passed,
                initial_total,
                initial_rate,
            )
            failures = self.failure_parser.parse_failures(output)
            if failures and len(failures) <= 10:
                logger.info(
                    "Attempting to fix %s failing tests individually...", len(failures)
                )
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
                        logger.info("✓ Fixed %s", failure["test_name"])
                    else:
                        logger.warning("✗ Could not fix %s", failure["test_name"])
                if fixed_count > 0:
                    logger.info(
                        "Re-running tests after fixing %s tests...", fixed_count
                    )
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
                            "execution_result": execution_result,
                            "message": f"Fixed {fixed_count} tests but file became corrupted",
                            "initial_score": f"{initial_passed}/{initial_total} ({initial_rate:.0f}%)",
                        }
                    final_result = await self.executor.execute_test(
                        test_file=test_file, code=modified_code
                    )
                    final_output = final_result.get("output", "")
                    final_passed = self._count_passed(final_output)
                    final_total = self._count_total(final_output)
                    final_rate = (
                        final_passed / final_total * 100 if final_total > 0 else 0
                    )
                    improvement = final_passed - initial_passed
                    if final_result.get("status") == "success":
                        logger.info(
                            "🎉 All tests now pass! (%s/%s = 100%)",
                            final_passed,
                            final_total,
                        )
                        logger.info(
                            "Fixed %s tests, improved by %s passing tests",
                            fixed_count,
                            improvement,
                        )
                        return {
                            "status": "success",
                            "message": f"All tests pass (fixed {fixed_count} individual test failures)",
                            "tests_fixed": fixed_count,
                            "initial_score": f"{initial_passed}/{initial_total} ({initial_rate:.0f}%)",
                            "final_score": f"{final_passed}/{final_total} ({final_rate:.0f}%)",
                        }
                    else:
                        logger.info(
                            "Final results: %s/%s tests pass (%s%)",
                            final_passed,
                            final_total,
                            final_rate,
                        )
                        logger.info("Improvement: +%s passing tests", improvement)
                        return {
                            "status": "tests_created_with_failures",
                            "test_file": test_file,
                            "execution_result": final_result,
                            "message": f"Tests generated, fixed {fixed_count} failures, but some still fail",
                            "tests_fixed": fixed_count,
                            "initial_score": f"{initial_passed}/{initial_total} ({initial_rate:.0f}%)",
                            "final_score": f"{final_passed}/{final_total} ({final_rate:.0f}%)",
                        }
            return {
                "status": "tests_created_with_failures",
                "test_file": test_file,
                "execution_result": execution_result,
                "message": "Tests were successfully generated but had runtime failures",
                "initial_score": f"{initial_passed}/{initial_total} ({initial_rate:.0f}%)",
            }
        else:
            return execution_result

    async def _check_complexity(self, module_path: str) -> bool:
        """Check if module complexity is acceptable."""
        try:
            full_path = settings.REPO_PATH / module_path
            complexity_check = self.complexity_filter.should_attempt(full_path)
            if not complexity_check["should_attempt"]:
                logger.warning("Skipping %s due to complexity filter", module_path)
                return False
            return True
        except Exception as exc:
            logger.warning("Complexity check failed for {module_path}: %s", exc)
            return False

    async def _generate_initial_code(
        self, module_context: ModuleContext, goal: str, target_coverage: float
    ) -> str | None:
        """Generate initial test code via LLM."""
        prompt = self.prompt_builder.build(module_context, goal, target_coverage)
        llm_client = await self.cognitive.aget_client_for_role("Coder")
        raw_response = await llm_client.make_request_async(prompt, user_id="test_gen")
        code = self.code_extractor.extract(raw_response)
        if not code:
            self._save_debug_artifact("failed_extract", raw_response or "")
        return code

    async def _validate_code(
        self, test_file: str, code: str, module_context: ModuleContext
    ) -> list[dict[str, Any]]:
        """
        Validate code and return violations.

        Returns empty list if valid.
        """
        violations = []
        if not self._looks_like_real_tests(
            code, module_context.import_path, module_context.module_path
        ):
            violations.append(
                {
                    "message": "Generated code does not look like a valid test file.",
                    "severity": "error",
                    "rule": "structural_sanity",
                }
            )
            return violations
        validation = await validate_code_async(
            test_file, code, auditor_context=self.auditor
        )
        if validation.get("status") == "dirty":
            violations.extend(validation.get("violations", []))
        return violations

    @staticmethod
    def _looks_like_real_tests(
        code: str, module_import_path: str, module_path: str
    ) -> bool:
        """Quick heuristic check if code looks like valid tests."""
        if not code:
            return False
        lowered = code.lower()
        has_test_def = "def test_" in lowered or "class test" in lowered
        has_assert = "assert " in lowered or "pytest.raises" in lowered
        return has_test_def and has_assert

    @staticmethod
    def _count_passed(pytest_output: str) -> int:
        """Extract passed test count from pytest output."""
        import re

        match = re.search("(\\d+) passed", pytest_output)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _count_total(pytest_output: str) -> int:
        """Extract total test count from pytest output."""
        import re

        passed_match = re.search("(\\d+) passed", pytest_output)
        failed_match = re.search("(\\d+) failed", pytest_output)
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        return passed + failed
