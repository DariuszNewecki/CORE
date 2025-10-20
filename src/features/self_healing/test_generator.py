# src/features/self_healing/test_generator.py
"""
Test generation service for autonomous coverage remediation.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from core.validation_pipeline import validate_code_async
from shared.config import settings
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext

log = getLogger(__name__)


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

    async def generate_test(
        self,
        module_path: str,
        test_file: str,
        goal: str,
        target_coverage: float,
    ) -> dict[str, Any]:
        """
        Generates and validates a single test file.
        """
        try:
            prompt = self._build_prompt(module_path, goal, target_coverage)
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(prompt, user_id="test_generator")

            test_code = self._extract_code_block(response)
            if not test_code:
                preview = (response or "")[:500]
                log.error(
                    "Failed to extract code from response. Response preview: %s",
                    preview,
                )
                return {"status": "failed", "error": "No code block in response"}

            validation_result = await validate_code_async(
                test_file,
                test_code,
                auditor_context=self.auditor,
            )

            if validation_result.get("status") == "dirty":
                log.warning(
                    "Validation failed for %s: %s",
                    test_file,
                    validation_result.get("violations", []),
                )

                # --- THIS IS THE FIX ---
                # Save the failed code to the reports directory for debugging.
                failed_dir = settings.REPO_PATH / "reports" / "failed_test_generation"
                failed_dir.mkdir(parents=True, exist_ok=True)
                failed_path = failed_dir / f"failed_{Path(test_file).name}"
                failed_path.write_text(test_code, encoding="utf-8")
                log.error(f"Saved syntactically incorrect test code to: {failed_path}")
                # --- END OF FIX ---

                return {
                    "status": "failed",
                    "error": "Validation failed",
                    "violations": validation_result.get("violations", []),
                }

            test_path = settings.REPO_PATH / test_file
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(
                validation_result.get("code", test_code), encoding="utf-8"
            )

            test_result = await self._run_test_async(test_file)

            return {
                "status": "success" if test_result["passed"] else "failed",
                "goal": goal,
                "test_file": test_file,
                "test_result": test_result,
            }

        except Exception as e:
            log.error("Failed to generate test: %s", e, exc_info=True)
            return {"status": "failed", "error": str(e)}

    def _build_prompt(
        self,
        module_path: str,
        goal: str,
        target_coverage: float,
    ) -> str:
        module_full_path = settings.REPO_PATH / module_path
        module_code = (
            module_full_path.read_text(encoding="utf-8")
            if module_full_path.exists()
            else f"# Module not found: {module_path}"
        )

        safe_module_name = module_full_path.stem
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

        return self.pipeline.process(filled_prompt)

    def _extract_code_block(self, response: str) -> str | None:
        if not response:
            return None
        patterns = [
            r"```python\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                code = matches[0].strip()
                if self._looks_like_python(code):
                    return code
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
        if self._looks_like_python(response):
            return response.strip()
        log.warning("Could not extract valid Python code from LLM response")
        return None

    def _looks_like_python(self, code: str) -> bool:
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
                await asyncio.wait_for(proc.wait(), timeout=5.0)
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
            log.error("Exception running test %s: %s", e, exc_info=True)
            return {
                "passed": False,
                "output": "",
                "errors": f"Test execution failed: {str(e)}",
                "returncode": -1,
            }
