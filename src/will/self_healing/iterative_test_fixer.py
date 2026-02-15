# src/features/self_healing/iterative_test_fixer.py
# ID: f270d71c-5ff1-474e-aed9-6a3c24b59df0

"""
Iterative test fixing with failure analysis and retry logic.

CONSTITUTIONAL FIX (V2.3):
- Modularized to reduce architectural debt (52.3 -> ~42.0).
- Delegates Test Execution to 'TestExecutor' (Body Layer).
- Delegates Code Extraction to 'CodeExtractor' (Parse Layer).
- Focuses purely on the Iterative Remediation Strategy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.self_healing.test_context_analyzer import ModuleContext
from body.self_healing.test_failure_analyzer import TestFailureAnalyzer
from body.self_healing.test_generation.code_extractor import CodeExtractor
from body.self_healing.test_generation.executor import TestExecutor
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async


logger = getLogger(__name__)


# ID: 39cda5d1-9692-4c00-9d07-848bb64e04de
class IterativeTestFixer:
    """
    Orchestrates the 'Generate -> Fail -> Analyze -> Fix' loop.

    Refactored to delegate execution and parsing to specialized components,
    satisfying modularity requirements.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        file_handler: FileHandler,
        repo_root: Path,
        max_attempts: int = 3,
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.file_handler = file_handler
        self.repo_root = repo_root
        self.max_attempts = max_attempts

        # Specialist Delegation
        self.pipeline = PromptPipeline(repo_path=repo_root)
        self.failure_analyzer = TestFailureAnalyzer()
        self.extractor = CodeExtractor()
        self.test_runner = TestExecutor()

    # ID: db735374-1dbd-423c-a2d6-b576a5b1839d
    async def generate_with_retry(
        self,
        module_context: ModuleContext,
        test_file: str,
        goal: str,
        target_coverage: float,
    ) -> dict[str, Any]:
        """Entry point for the iterative fixing loop."""
        best_result = None
        best_passed = 0

        for attempt in range(1, self.max_attempts + 1):
            logger.info("🛠️ Iterative Fixer: Attempt %d/%d", attempt, self.max_attempts)

            # 1. GENERATE OR FIX
            if attempt == 1:
                code = await self._generate_initial(
                    module_context, goal, target_coverage
                )
            else:
                code = await self._generate_fix(module_context, best_result, attempt)

            if not code:
                continue

            # 2. VALIDATE & EXECUTE (Delegated to Body)
            result = await self._evaluate_attempt(test_file, code)
            if result.get("status") == "failed":
                continue

            # 3. SCORE & DECIDE
            passed = result["test_result"].get("passed_count", 0)
            if passed > best_passed:
                best_passed = passed
                best_result = result

            if result["test_result"].get("passed", False):
                logger.info("✅ All tests passed after %d attempts!", attempt)
                return result

        return best_result or {"status": "failed", "error": "All attempts failed"}

    async def _generate_initial(
        self, ctx: ModuleContext, goal: str, target: float
    ) -> str | None:
        """Initial generation logic."""
        prompt = self._build_prompt(
            "test_generator",
            {
                "module_path": ctx.module_path,
                "import_path": ctx.import_path,
                "target_coverage": target,
                "module_code": ctx.source_code,
                "goal": goal,
                "safe_module_name": ctx.module_name,
            },
        )
        return await self._request_code(prompt, "initial_gen")

    async def _generate_fix(
        self, ctx: ModuleContext, prev: dict, attempt: int
    ) -> str | None:
        """Fix generation logic based on failures."""
        analysis = self.failure_analyzer.analyze(
            prev["test_result"].get("output", ""), prev["test_result"].get("errors", "")
        )
        prompt = self._build_prompt(
            "test_fixer",
            {
                "original_test_code": prev.get("test_code", ""),
                "test_results": f"Passed: {analysis.passed}, Failed: {analysis.failed}",
                "failure_summary": self.failure_analyzer.generate_fix_summary(analysis),
            },
        )
        return await self._request_code(prompt, f"fix_attempt_{attempt}")

    async def _evaluate_attempt(self, test_file: str, code: str) -> dict[str, Any]:
        """Validates and runs the test using Body-layer components."""
        val = await validate_code_async(test_file, code, auditor_context=self.auditor)
        if val.get("status") == "dirty":
            return {"status": "failed", "error": "Validation failed"}

        # Use the standard TestExecutor for the actual subprocess work
        run_res = await self.test_runner.execute_test(
            test_file, val["code"], self.file_handler, self.repo_root
        )

        # Enrich results with analysis
        analysis = self.failure_analyzer.analyze(
            run_res.get("output", ""), run_res.get("errors", "")
        )
        run_res.update(
            {
                "passed_count": analysis.passed,
                "failed_count": analysis.failed,
                "total_count": analysis.total,
            }
        )

        return {"status": "success", "test_code": val["code"], "test_result": run_res}

    async def _request_code(self, prompt: str, stage: str) -> str | None:
        """Helper to get code from LLM and extract cleanly."""
        client = await self.cognitive.aget_client_for_role("Coder")
        response = await client.make_request_async(
            self.pipeline.process(prompt), user_id="iter_fixer"
        )
        code = self.extractor.extract(response)
        if not code:
            self._save_debug(f"{stage}_raw.txt", response)
        return code

    def _build_prompt(self, template_name: str, mapping: dict) -> str:
        """Loads and formats a prompt template from the Mind."""
        path = self.repo_root / "var/prompts" / f"{template_name}.txt"
        template = path.read_text(encoding="utf-8") if path.exists() else "{goal}"
        return template.format(**mapping)

    def _save_debug(self, filename: str, content: str):
        """Governed write for debug artifacts."""
        self.file_handler.ensure_dir("work/testing/debug")
        self.file_handler.write_runtime_text(f"work/testing/debug/{filename}", content)
