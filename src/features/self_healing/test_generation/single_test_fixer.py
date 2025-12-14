# src/features/self_healing/test_generation/single_test_fixer.py

"""
Single Test Fixer - fixes individual failing tests with focused LLM prompts.

Philosophy: One test, one error, one fix. Keep it simple and focused.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline


logger = getLogger(__name__)


# ID: 13a03b46-5cbe-46ea-824a-5a8e506fb7fb
class TestFailureParser:
    """Parses pytest output to extract individual test failures."""

    @staticmethod
    # ID: c12c580d-786f-42a0-b29d-525ffdf81db0
    def parse_failures(pytest_output: str) -> list[dict[str, Any]]:
        """
        Extract structured failure info from pytest output.

        Returns list of:
        {
            "test_name": "test_something",
            "test_path": "tests/test_file.py::TestClass::test_something",
            "failure_type": "AssertionError",
            "error_message": "assert 'root' == ''",
            "line_number": 39,
            "full_traceback": "...",
        }
        """
        failures = []
        failed_pattern = "FAILED ([\\w/\\.]+::[\\w:]+) - (.+)"
        for match in re.finditer(failed_pattern, pytest_output):
            test_path = match.group(1)
            error_type = match.group(2)
            parts = test_path.split("::")
            test_name = parts[-1] if parts else "unknown"
            section_pattern = f"_{{{len(parts[-1])}_}} {test_name} _{{{len(parts[-1])}_}}(.*?)(?=_{{{(10,)}}}|$)"
            section_match = re.search(section_pattern, pytest_output, re.DOTALL)
            full_traceback = section_match.group(1).strip() if section_match else ""
            error_message = ""
            line_number = None
            for line in full_traceback.split("\n"):
                if line.strip().startswith("E "):
                    error_message = line.strip()[2:]
                    if not error_message or error_message.startswith("AssertionError"):
                        continue
                    break
                if "test_" in line and ".py:" in line:
                    line_match = re.search(":(\\d+):", line)
                    if line_match:
                        line_number = int(line_match.group(1))
            failures.append(
                {
                    "test_name": test_name,
                    "test_path": test_path,
                    "failure_type": error_type,
                    "error_message": error_message or error_type,
                    "line_number": line_number,
                    "full_traceback": full_traceback,
                }
            )
        return failures


# ID: fc61a613-0357-40e0-ba52-9082ff874b8a
class TestExtractor:
    """Extracts individual test functions from test files."""

    @staticmethod
    # ID: 7f3249d6-5e80-45ea-9e25-19e4e42030d0
    def extract_test_function(file_path: Path, test_name: str) -> str | None:
        """
        Extract the source code of a specific test function.

        Returns the complete function definition including decorators.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == test_name:
                    return ast.get_source_segment(content, node)
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == test_name:
                            class_source = ast.get_source_segment(content, node)
                            return class_source
            return None
        except Exception as e:
            logger.warning("Failed to extract test function {test_name}: %s", e)
            return None

    @staticmethod
    # ID: b3943163-5281-4ec4-a75e-180ce9dee743
    def replace_test_function(
        file_path: Path, test_name: str, new_function_code: str
    ) -> bool:
        """
        Replace a test function in the file with new code.

        Returns True if successful.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            try:
                ast.parse(new_function_code)
            except SyntaxError as e:
                logger.error("New function code has syntax error: %s", e)
                return False
            replaced = False
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == test_name:
                    original = ast.get_source_segment(content, node)
                    if original:
                        new_content = content.replace(original, new_function_code, 1)
                        try:
                            ast.parse(new_content)
                        except SyntaxError as e:
                            logger.error("Replacement would corrupt file: %s", e)
                            return False
                        file_path.write_text(new_content, encoding="utf-8")
                        replaced = True
                        break
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == test_name:
                            original = ast.get_source_segment(content, item)
                            if original:
                                new_content = content.replace(
                                    original, new_function_code, 1
                                )
                                try:
                                    ast.parse(new_content)
                                except SyntaxError as e:
                                    logger.error(
                                        "Replacement would corrupt file: %s", e
                                    )
                                    return False
                                file_path.write_text(new_content, encoding="utf-8")
                                replaced = True
                                break
                    if replaced:
                        break
            return replaced
        except Exception as e:
            logger.error("Failed to replace test function {test_name}: %s", e)
            return False


# ID: bf2b0925-d12c-49f5-ae16-0dd3cb9d06f8
class SingleTestFixer:
    """
    Fixes individual failing tests using focused LLM prompts.

    Strategy: One test, one error, one focused fix.
    """

    def __init__(self, cognitive_service: CognitiveService, max_attempts: int = 3):
        self.cognitive = cognitive_service
        self.max_attempts = max_attempts
        self.parser = TestFailureParser()
        self.extractor = TestExtractor()

    # ID: 8adb4bee-9216-47a3-9d96-ec9714bb5daf
    async def fix_test(
        self,
        test_file: Path,
        test_name: str,
        failure_info: dict[str, Any],
        source_file: Path | None = None,
    ) -> dict[str, Any]:
        """
        Fix a single failing test.

        Args:
            test_file: Path to test file
            test_name: Name of failing test function
            failure_info: Parsed failure information
            source_file: Optional source file being tested

        Returns:
            {
                "status": "fixed" | "unfixable" | "error",
                "attempts": int,
                "final_error": str (if unfixable),
            }
        """
        logger.info("Attempting to fix test: %s", test_name)
        test_code = self.extractor.extract_test_function(test_file, test_name)
        if not test_code:
            return {
                "status": "error",
                "error": f"Could not extract test function {test_name}",
            }
        source_context = ""
        if source_file and source_file.exists():
            try:
                source_context = source_file.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass
        for attempt in range(self.max_attempts):
            logger.info(
                "Fix attempt %s/%s for %s", attempt + 1, self.max_attempts, test_name
            )
            prompt = self._build_fix_prompt(
                test_name=test_name,
                test_code=test_code,
                failure_info=failure_info,
                source_context=source_context,
                attempt=attempt,
            )
            try:
                llm_client = await self.cognitive.aget_client_for_role("Coder")
                response = await llm_client.make_request_async(
                    prompt, user_id="test_fixer"
                )
                fixed_code = self._extract_fixed_code(response)
                if not fixed_code:
                    logger.warning("Could not extract fixed code from LLM response")
                    continue
                try:
                    ast.parse(fixed_code)
                except SyntaxError as e:
                    logger.warning("Fixed code has syntax error: %s", e)
                    continue
                if not self.extractor.replace_test_function(
                    test_file, test_name, fixed_code
                ):
                    logger.warning("Could not apply fix to %s", test_name)
                    continue
                logger.info("Successfully applied fix to %s", test_name)
                return {"status": "fixed", "attempts": attempt + 1}
            except Exception as e:
                logger.error("Error during fix attempt: %s", e)
                continue
        return {
            "status": "unfixable",
            "attempts": self.max_attempts,
            "final_error": failure_info.get("error_message"),
        }

    def _build_fix_prompt(
        self,
        test_name: str,
        test_code: str,
        failure_info: dict[str, Any],
        source_context: str,
        attempt: int,
    ) -> str:
        """Build a focused prompt for fixing this specific test."""
        error_msg = failure_info.get("error_message", "Unknown error")
        traceback = failure_info.get("full_traceback", "")
        base_prompt = f"You are a test fixing specialist. Fix this ONE failing test.\n\nTEST FUNCTION: {test_name}\nFAILURE TYPE: {failure_info.get('failure_type', 'Unknown')}\n\nERROR MESSAGE:\n{error_msg}\n\nCURRENT TEST CODE:\n```python\n{test_code}\n```\n\nFAILURE DETAILS:\n{traceback[:500]}\n\nSOURCE CODE CONTEXT (if relevant):\n{(source_context[:500] if source_context else 'Not available')}\n\nYOUR TASK:\n1. Analyze why this specific test is failing\n2. Fix the test to be correct and meaningful\n3. Output ONLY the fixed test function (complete, ready to replace)\n\nCRITICAL RULES:\n- Output the COMPLETE test function, including decorator and docstring\n- The test must be valid Python\n- The test should test something meaningful\n- If the test has wrong expectations, fix the assertion\n- If the test data is problematic, fix the data\n- Keep the same function name: {test_name}\n\nRESPOND WITH:\n```python\ndef {test_name}(...):\n    # Fixed test here\n```\n\nDO NOT include explanations, just the fixed code.\n"
        pipeline = PromptPipeline(repo_path=settings.REPO_PATH)
        return pipeline.process(base_prompt)

    def _extract_fixed_code(self, llm_response: str) -> str | None:
        """Extract the fixed test function from LLM response."""
        match = re.search("```python\\s*\\n(.*?)\\n```", llm_response, re.DOTALL)
        if match:
            return match.group(1).strip()
        lines = llm_response.strip().split("\n")
        if lines[0].strip().startswith("def "):
            return llm_response.strip()
        return None
