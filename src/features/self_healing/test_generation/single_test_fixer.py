# src/features/self_healing/test_generation/single_test_fixer.py
# ID: bf2b0925-d12c-49f5-ae16-0dd3cb9d06f8

"""
Single Test Fixer - Refined A3 Orchestrator.

CONSTITUTIONAL FIX (V2.3.10):
- Modularized to clear Modularity Debt (49.1 -> ~28.0).
- Delegates parsing to 'TestFailureParser'.
- Delegates file manipulation to 'TestExtractor'.
- Focuses purely on AI fix orchestration.
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger
from will.orchestration.prompt_pipeline import PromptPipeline

# CONSTITUTIONAL FIX: Relative imports of our new specialists
from .failure_parser import TestFailureParser
from .test_extractor import TestExtractor


logger = getLogger(__name__)


# ID: 226f618b-5aff-43fc-86f8-a80ac937ea31
class SingleTestFixer:
    """Orchestrates individual test repairs using specialists."""

    def __init__(self, cognitive_service, file_handler, repo_root, max_attempts=3):
        self.cognitive = cognitive_service
        self.max_attempts = max_attempts
        self.repo_root = repo_root

        # Specialists
        self.parser = TestFailureParser()
        self.extractor = TestExtractor(file_handler, repo_root)
        self.pipeline = PromptPipeline(repo_path=repo_root)

    # ID: 8adb4bee-9216-47a3-9d96-ec9714bb5daf
    async def fix_test(
        self,
        test_file: Path,
        test_name: str,
        failure_info: dict,
        source_file: Path | None = None,
    ) -> dict:
        """AI Orchestration loop for fixing a specific test."""
        test_code = self.extractor.extract_test_function(test_file, test_name)
        if not test_code:
            return {"status": "error", "error": "Source extraction failed"}

        for attempt in range(self.max_attempts):
            logger.info(
                "🤖 Fix Attempt %d/%d for %s", attempt + 1, self.max_attempts, test_name
            )

            prompt = self._build_prompt(test_name, test_code, failure_info)
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(
                self.pipeline.process(prompt), user_id="test_fixer"
            )

            fixed_code = self._extract_code(response)
            if fixed_code and self.extractor.replace_test_function(
                test_file, test_name, fixed_code
            ):
                return {"status": "fixed", "attempt": attempt + 1}

        return {"status": "failed"}

    def _build_prompt(self, name: str, code: str, info: dict) -> str:
        return f"Fix this failing test: {name}\nError: {info.get('failure_type')}\nCode:\n{code}"

    def _extract_code(self, response: str) -> str | None:
        """Simple extraction logic helper."""
        if "```python" in response:
            return response.split("```python")[1].split("```")[0].strip()
        return response.strip()
