# src/features/self_healing/simple_test_generator.py

"""
Ultra-simple test generator: one symbol at a time, keep what works.

This REPLACES the complex TestGenerator/EnhancedTestGenerator/IterativeTestFixer stack.
Philosophy: 40% success rate with simple approach > 30% with complex approach.

Constitutional Principles: clarity_first, safe_by_default
"""

from __future__ import annotations

import ast
import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 21623149-488d-43c8-9056-1bf255428dde
class SimpleTestGenerator:
    """
    Generates tests for individual symbols (functions/classes) one at a time.

    Key design principles:
    - No complex context analysis (just the symbol source)
    - No iterative fixing (accept or skip)
    - No full-file testing (accumulate symbol by symbol)
    - Fail fast (10s timeout per test)
    """

    def __init__(self, cognitive_service: CognitiveService):
        """Initialize with just the LLM service."""
        self.cognitive = cognitive_service

    # ID: cf4829fd-5d26-44f2-b5af-219528cd77c3
    async def generate_test_for_symbol(
        self, file_path: str, symbol_name: str
    ) -> dict[str, Any]:
        """
        Generate a test for ONE symbol.

        Args:
            file_path: Path to source file (e.g., "src/core/foo.py")
            symbol_name: Name of function/class to test

        Returns:
            {
                "status": "success" | "skipped" | "failed",
                "test_code": str | None,
                "passed": bool,
                "reason": str  # Why it succeeded/failed
            }
        """
        try:
            symbol_code = self._extract_symbol_code(file_path, symbol_name)
            if not symbol_code:
                return {
                    "status": "skipped",
                    "test_code": None,
                    "passed": False,
                    "reason": f"Could not extract {symbol_name} from {file_path}",
                }
            test_code = await self._generate_test_code(
                file_path, symbol_name, symbol_code
            )
            if not test_code:
                return {
                    "status": "failed",
                    "test_code": None,
                    "passed": False,
                    "reason": "LLM did not return valid code",
                }
            passed, error = await self._try_run_test(test_code, symbol_name)
            if passed:
                return {
                    "status": "success",
                    "test_code": test_code,
                    "passed": True,
                    "reason": "Test compiled and passed",
                }
            else:
                return {
                    "status": "failed",
                    "test_code": test_code,
                    "passed": False,
                    "reason": f"Test failed: {error[:200]}",
                }
        except Exception as e:
            logger.error(f"Error generating test for {symbol_name}: {e}")
            return {
                "status": "failed",
                "test_code": None,
                "passed": False,
                "reason": str(e),
            }

    def _extract_symbol_code(self, file_path: str, symbol_name: str) -> str | None:
        """Extract source code for a specific symbol using AST."""
        try:
            full_path = settings.REPO_PATH / file_path
            source = full_path.read_text(encoding="utf-8")
            lines = source.splitlines()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name == symbol_name:
                        start = node.lineno - 1
                        end = (
                            node.end_lineno
                            if hasattr(node, "end_lineno")
                            else start + 20
                        )
                        return "\n".join(lines[start:end])
            return None
        except Exception as e:
            logger.debug(f"Failed to extract {symbol_name}: {e}")
            return None

    async def _generate_test_code(
        self, file_path: str, symbol_name: str, symbol_code: str
    ) -> str | None:
        """Call LLM with ultra-simple prompt."""
        module_path = file_path.replace("src/", "").replace(".py", "").replace("/", ".")
        prompt = f'Generate a pytest test for this Python function from {file_path}:\n```python\n{symbol_code}\n```\n\nRequirements:\n- Write ONE test function named: test_{symbol_name}\n- Import the function like this: from {module_path} import {symbol_name}\n- Test the happy path only (basic functionality)\n- Use mocks if needed: from unittest.mock import MagicMock, AsyncMock, patch\n- Keep it simple - 5-15 lines\n- Output ONLY the test function in a ```python code block\n- DO NOT use placeholder imports like "from your_module import" - use the actual import path provided above\n\nExample format:\n```python\ndef test_{symbol_name}():\n    from {module_path} import {symbol_name}\n    # Your test here\n    assert True\n```\n'
        try:
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(
                prompt, user_id="simple_test_gen"
            )
            code = self._extract_code_block(response)
            return code
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return None

    def _extract_code_block(self, response: str) -> str | None:
        """Extract Python code from LLM response."""
        if not response:
            return None
        patterns = ["```python\\s*(.*?)\\s*```", "```\\s*(.*?)\\s*```"]
        for pattern in patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            if matches:
                code = matches[0].strip()
                if code and len(code) > 20:
                    return code
        if response.strip().startswith(("def ", "async def ", "import ", "from ")):
            return response.strip()
        return None

    async def _try_run_test(self, test_code: str, symbol_name: str) -> tuple[bool, str]:
        """
        Try to run the test. Return (passed, error_msg).

        Fast fail: 10 second timeout.
        """
        temp_dir = settings.REPO_PATH / "work" / "testing" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=temp_dir, encoding="utf-8"
        ) as f:
            content = f"# Auto-generated test for {symbol_name}\nimport pytest\nfrom unittest.mock import MagicMock, AsyncMock, patch\n\n{test_code}\n"
            f.write(content)
            temp_path = f.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "poetry",
                "run",
                "pytest",
                temp_path,
                "-v",
                "--tb=line",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=10.0
                )
            except TimeoutError:
                proc.kill()
                return (False, "Test timed out after 10 seconds")
            if proc.returncode == 0:
                return (True, "")
            else:
                error = stderr.decode("utf-8", errors="replace")
                return (False, error)
        except Exception as e:
            return (False, str(e))
        finally:
            Path(temp_path).unlink(missing_ok=True)
