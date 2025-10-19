# src/features/self_healing/test_generator.py
"""
Test generation service for autonomous coverage remediation.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from core.validation_pipeline import validate_code_async
from shared.config import settings
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext

log = getLogger(__name__)


# ID: e4a619f6-3b6c-4c85-ae3d-cef8f811e935
class TestGenerator:
    """Generates and validates test files for modules."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.pipeline = PromptPipeline(repo_path=settings.REPO_PATH)
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Loads the test generation prompt from the constitutional prompt directory."""
        prompt_path = settings.get_path("mind.prompts.test_generator")
        if not prompt_path or not prompt_path.exists():
            raise FileNotFoundError(
                "Test generator prompt not found. Please ensure it's in meta.yaml and exists."
            )
        return prompt_path.read_text(encoding="utf-8")

    # ID: 350146a9-3043-4271-afb9-9bccb6aca6a5
    async def generate_test(
        self,
        module_path: str,
        test_file: str,
        goal: str,
        target_coverage: float,
    ) -> dict[str, Any]:
        """
        Generates and validates a single test file.

        Args:
            module_path: Path to module being tested
            test_file: Path where test should be written
            goal: Description of testing goal
            target_coverage: Target coverage percentage

        Returns:
            Dict with generation result and metrics
        """
        try:
            # Build test generation prompt
            prompt = self._build_prompt(module_path, goal, target_coverage)

            # Get AI client for code generation
            client = await self.cognitive.aget_client_for_role("Coder")

            # Generate test code
            response = await client.make_request_async(
                prompt,
                user_id="test_generator",
            )

            # Extract code from response
            test_code = self._extract_code_block(response)
            if not test_code:
                log.error(
                    f"Failed to extract code from response. Response preview: {response[:500]}"
                )
                return {"status": "failed", "error": "No code block in response"}

            # Validate the generated test
            validation_result = await validate_code_async(
                test_file,
                test_code,
                auditor_context=self.auditor,
            )

            if validation_result.get("status") == "dirty":
                log.warning(
                    f"Validation failed for {test_file}: {validation_result.get('violations', [])}"
                )
                return {
                    "status": "failed",
                    "error": "Validation failed",
                    "violations": validation_result["violations"],
                }

            # Write test file
            test_path = settings.REPO_PATH / test_file
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(validation_result["code"], encoding="utf-8")

            # Run the test
            test_result = await self._run_test_async(test_file)

            return {
                "status": "success" if test_result["passed"] else "failed",
                "goal": goal,
                "test_file": test_file,
                "test_result": test_result,
            }

        except Exception as e:
            log.error(f"Failed to generate test: {e}", exc_info=True)
            return {"status": "failed", "error": str(e)}

    def _build_prompt(
        self,
        module_path: str,
        goal: str,
        target_coverage: float,
    ) -> str:
        """Builds a comprehensive prompt for test generation using the template."""
        module_full_path = settings.REPO_PATH / module_path

        if not module_full_path.exists():
            module_code = f"# Module not found: {module_path}"
        else:
            module_code = module_full_path.read_text(encoding="utf-8")

        safe_module_name = module_full_path.stem
        # Correctly derive the import path from the repo-relative path
        import_path = (
            module_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )

        filled_prompt = self.prompt_template.format(
            module_path=module_path,
            target_coverage=target_coverage,
            module_code=module_code,
            goal=goal,
            safe_module_name=safe_module_name,
            import_path=import_path,
        )

        # The giant hardcoded string has been removed. The prompt file is now the SSOT.
        return self.pipeline.process(filled_prompt)

    def _extract_code_block(self, response: str) -> str | None:
        """Extracts Python code from markdown or raw response."""
        # This function is now more robust to handle different LLM output styles
        if not response:
            return None

        # Pattern 1: Standard markdown python blocks
        pattern = r"```python\s*(.*?)\s*```"
        matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
        if matches:
            code = matches[0].strip()
            if self._looks_like_python(code):
                return code

        # Pattern 2: Generic code blocks
        pattern = r"```\s*(.*?)\s*```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            code = matches[0].strip()
            if self._looks_like_python(code):
                return code

        # Pattern 3: Look for Python code without fences
        lines = response.split("\n")
        start_idx = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(
                ("import ", "from ", "def ", "class ", "@pytest", "# test")
            ):
                start_idx = i
                break
        if start_idx is not None:
            code = "\n".join(lines[start_idx:]).strip()
            if self._looks_like_python(code):
                return code

        # Pattern 4: If the whole response looks like Python
        if self._looks_like_python(response):
            return response.strip()

        log.warning("Could not extract valid Python code from LLM response")
        return None

    def _looks_like_python(self, code: str) -> bool:
        """A simple heuristic to check if a string contains Python code."""
        code = (code or "").strip()
        if not code:
            return False
        python_indicators = [
            "import ",
            "from ",
            "def ",
            "class ",
            "async def",
            "pytest",
            "@",
            "assert",
            "return",
            "if ",
            "for ",
            "while ",
        ]
        return any(indicator in code for indicator in python_indicators)

    async def _run_test_async(self, test_file: str) -> dict[str, Any]:
        """Runs a specific test file asynchronously and returns results."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "poetry",
                "run",
                "pytest",
                "--envfile",
                ".env.test",
                test_file,
                "-v",
                "--tb=short",
                cwd=settings.REPO_PATH,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=120.0
                )
            except TimeoutError:
                proc.kill()
                await asyncio.wait_for(
                    proc.wait(), timeout=5.0
                )  # Ensure process is terminated
                return {
                    "passed": False,
                    "output": "",
                    "errors": "Test execution timed out after 120 seconds",
                    "returncode": -1,
                }

            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")

            return {
                "passed": proc.returncode == 0,
                "output": output,
                "errors": errors,
                "returncode": proc.returncode,
            }

        except Exception as e:
            log.error(f"Exception running test {test_file}: {e}", exc_info=True)
            return {
                "passed": False,
                "output": "",
                "errors": f"Test execution failed: {str(e)}",
                "returncode": -1,
            }
