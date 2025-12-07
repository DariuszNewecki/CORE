# src/features/self_healing/iterative_test_fixer.py

"""
Iterative test fixing with failure analysis and retry logic.

This service implements the human debugging workflow:
1. Generate tests
2. Run tests
3. If failures, analyze what went wrong
4. Fix the tests based on failure analysis
5. Retry (up to max attempts)
"""

from __future__ import annotations

import asyncio
from typing import Any

from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async

from features.self_healing.test_context_analyzer import ModuleContext
from features.self_healing.test_failure_analyzer import TestFailureAnalyzer

logger = getLogger(__name__)


# ID: 557c4191-5dfc-4b5c-bb31-0bc6e1f389a3
class IterativeTestFixer:
    """
    Generates and iteratively fixes tests based on failure analysis.

    This implements a retry loop:
    - Attempt 1: Generate tests with full context
    - Attempt 2-3: Fix tests based on failure analysis

    Returns the best result across all attempts.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        max_attempts: int = 3,
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.pipeline = PromptPipeline(repo_path=settings.REPO_PATH)
        self.failure_analyzer = TestFailureAnalyzer()
        self.max_attempts = max_attempts
        self.initial_prompt_template = self._load_prompt("test_generator")
        self.fix_prompt_template = self._load_prompt("test_fixer")

    def _load_prompt(self, name: str) -> str:
        """Load prompt template from constitutional prompts."""
        try:
            prompt_path = settings.get_path(f"mind.prompts.{name}")
            if prompt_path and prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
        except Exception:
            pass
        if name == "test_fixer":
            logger.info("Using default test_fixer prompt (not in meta.yaml)")
            return self._get_default_fix_prompt()
        raise FileNotFoundError(f"Prompt not found: {name}")

    def _get_default_fix_prompt(self) -> str:
        """Default prompt for fixing tests."""
        return "# Test Fixing Task\n\nYou previously generated tests, but some failed. Your task is to fix ONLY the failing tests while keeping passing tests unchanged.\n\n## Original Test Code\n```python\n{original_test_code}\n```\n\n## Test Results\n{test_results}\n\n## Failure Analysis\n{failure_summary}\n\n## Your Task\n1. Analyze why each test failed\n2. Fix ONLY the failing tests\n3. Keep all passing tests exactly the same\n4. Output the complete corrected test file\n\n## Common Fixes\n- **AssertionError (values don't match)**: Update expected value to match actual\n- **Off-by-one errors**: Adjust counts/indices\n- **Empty vs None**: Check if function returns empty list [] vs None\n- **Extra/missing items**: Verify list lengths and contents\n- **Type errors**: Ensure correct types in assertions\n\n## Critical Rules\n- Do NOT modify passing tests\n- Output complete, valid Python code\n- Use same imports and structure\n- Single code block with ```python\n\nGenerate the corrected test file now.\n"

    # ID: 511f0b00-6d6c-4894-8875-f4b80a72eafa
    async def generate_with_retry(
        self,
        module_context: ModuleContext,
        test_file: str,
        goal: str,
        target_coverage: float,
    ) -> dict[str, Any]:
        """
        Generate tests with iterative fixing based on failures.

        Args:
            module_context: Rich context about the module
            test_file: Path where test should be written
            goal: High-level testing goal
            target_coverage: Target coverage percentage

        Returns:
            Best result across all attempts with metrics
        """
        best_result = None
        best_passed = 0

        logger.info(
            "Iterative Test Generation: Starting (max %d attempts)", self.max_attempts
        )

        for attempt in range(1, self.max_attempts + 1):
            logger.info("Attempt %d/%d", attempt, self.max_attempts)

            if attempt == 1:
                result = await self._generate_initial(
                    module_context, test_file, goal, target_coverage
                )
            else:
                result = await self._fix_based_on_failures(
                    module_context, test_file, best_result, attempt
                )

            if not result or result.get("status") == "failed":
                logger.warning("Attempt %d failed to generate valid tests", attempt)
                continue

            test_results = result.get("test_result", {})
            passed = test_results.get("passed_count", 0)
            total = test_results.get("total_count", 0)

            logger.info("Results: %d/%d tests passed", passed, total)

            if passed > best_passed:
                best_passed = passed
                best_result = result

            if test_results.get("passed", False):
                logger.info("All tests passed!")
                return result

            logger.info("%d tests need fixing", total - passed)

        logger.warning(
            "Iterative generation finished. Best result: %d tests passing", best_passed
        )
        return best_result or {"status": "failed", "error": "All attempts failed"}

    async def _generate_initial(
        self, context: ModuleContext, test_file: str, goal: str, target_coverage: float
    ) -> dict[str, Any]:
        """Generate initial tests with full context (Attempt 1)."""
        try:
            prompt = self._build_initial_prompt(context, goal, target_coverage)
            self._save_debug_artifact("prompt_attempt_1.txt", prompt)
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(prompt, user_id="test_gen_iter")
            test_code = self._extract_code_block(response)
            if not test_code:
                return {"status": "failed", "error": "No code generated"}
            return await self._validate_and_run(test_file, test_code)
        except Exception as e:
            logger.error(f"Initial generation failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def _fix_based_on_failures(
        self,
        context: ModuleContext,
        test_file: str,
        previous_result: dict[str, Any],
        attempt: int,
    ) -> dict[str, Any]:
        """Fix tests based on previous attempt's failures."""
        try:
            previous_code = previous_result.get("test_code", "")
            test_result = previous_result.get("test_result", {})
            failure_analysis = self.failure_analyzer.analyze(
                test_result.get("output", ""), test_result.get("errors", "")
            )
            failure_summary = self.failure_analyzer.generate_fix_summary(
                failure_analysis
            )
            prompt = self._build_fix_prompt(
                context, previous_code, test_result, failure_summary, attempt
            )
            self._save_debug_artifact(f"prompt_attempt_{attempt}.txt", prompt)
            self._save_debug_artifact(
                f"failures_attempt_{attempt - 1}.txt", failure_summary
            )
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(prompt, user_id="test_fix_iter")
            test_code = self._extract_code_block(response)
            if not test_code:
                return {"status": "failed", "error": "No code generated in fix"}
            return await self._validate_and_run(test_file, test_code)
        except Exception as e:
            logger.error(f"Fix attempt {attempt} failed: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    async def _validate_and_run(self, test_file: str, test_code: str) -> dict[str, Any]:
        """Validate code and run tests."""
        validation_result = await validate_code_async(
            test_file, test_code, auditor_context=self.auditor
        )
        if validation_result.get("status") == "dirty":
            return {
                "status": "failed",
                "error": "Validation failed",
                "violations": validation_result.get("violations", []),
            }
        test_path = settings.REPO_PATH / test_file
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(test_code, encoding="utf-8")
        test_result = await self._run_test_async(test_file)
        enhanced_result = self._enhance_test_result(test_result)
        return {
            "status": "success" if enhanced_result["passed"] else "partial",
            "test_code": test_code,
            "test_file": test_file,
            "test_result": enhanced_result,
        }

    def _enhance_test_result(self, test_result: dict) -> dict:
        """Add parsed information to test result."""
        output = test_result.get("output", "")
        analysis = self.failure_analyzer.analyze(output, test_result.get("errors", ""))
        return {
            **test_result,
            "passed_count": analysis.passed,
            "failed_count": analysis.failed,
            "total_count": analysis.total,
            "success_rate": analysis.success_rate,
        }

    def _build_initial_prompt(
        self, context: ModuleContext, goal: str, target_coverage: float
    ) -> str:
        """Build initial test generation prompt with full context."""
        base_prompt = self.initial_prompt_template.format(
            module_path=context.module_path,
            import_path=context.import_path,
            target_coverage=target_coverage,
            module_code=context.source_code,
            goal=goal,
            safe_module_name=context.module_name,
        )
        enriched_prompt = f"# CRITICAL CONTEXT\n\n{context.to_prompt_context()}\n\n---\n\n{base_prompt}\n\n---\n\n# REMINDER\nFocus on these uncovered functions: {', '.join(context.uncovered_functions[:5])}\nMock: {(', '.join(context.external_deps) if context.external_deps else 'None needed')}\n"
        return self.pipeline.process(enriched_prompt)

    def _build_fix_prompt(
        self,
        context: ModuleContext,
        original_code: str,
        test_result: dict,
        failure_summary: str,
        attempt: int,
    ) -> str:
        """Build prompt for fixing tests based on failures."""
        prompt = self.fix_prompt_template.format(
            original_test_code=original_code,
            test_results=f"Passed: {test_result.get('passed_count', 0)}, Failed: {test_result.get('failed_count', 0)}",
            failure_summary=failure_summary,
        )
        prompt += f"\n\n## Module Being Tested\nPath: {context.module_path}\nImport: {context.import_path}\n\n## Fix Strategy for Attempt {attempt}\n{('Focus on assertion mismatches - check expected vs actual values' if attempt == 2 else 'Check edge cases and boundary conditions')}\n"
        return self.pipeline.process(prompt)

    def _extract_code_block(self, response: str) -> str | None:
        """Extract Python code from LLM response."""
        import re

        patterns = ["```python\\s*(.*?)\\s*```", "```\\s*(.*?)\\s*```"]
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                return matches[0].strip()
        if response.strip().startswith(("import ", "from ", "def ", "class ", "#")):
            return response.strip()
        return None

    async def _run_test_async(self, test_file: str) -> dict[str, Any]:
        """Execute tests and return results."""
        try:
            process = await asyncio.create_subprocess_exec(
                "pytest",
                str(settings.REPO_PATH / test_file),
                "-v",
                "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=settings.REPO_PATH,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            output = stdout.decode("utf-8")
            errors = stderr.decode("utf-8")
            passed = process.returncode == 0
            return {
                "passed": passed,
                "returncode": process.returncode,
                "output": output,
                "errors": errors,
            }
        except TimeoutError:
            return {
                "passed": False,
                "returncode": -1,
                "output": "",
                "errors": "Test execution timed out",
            }
        except Exception as e:
            return {"passed": False, "returncode": -1, "output": "", "errors": str(e)}

    def _save_debug_artifact(self, filename: str, content: str):
        """Save debugging artifact."""
        debug_dir = settings.REPO_PATH / "work" / "testing" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = debug_dir / filename
        artifact_path.write_text(content, encoding="utf-8")
        logger.debug("Saved debug artifact: %s", artifact_path)
