# src/features/self_healing/context_aware_test_generator.py
"""
Context-aware test generator using ContextPackage for better results.

This improves on SimpleTestGenerator by providing the LLM with:
- Full symbol dependencies (imports, related functions)
- Related test examples from the codebase
- Module structure and patterns
- Type hints and docstrings
"""

from __future__ import annotations

import ast
import asyncio
import tempfile
from pathlib import Path
from typing import Any

from services.context.service import ContextService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.orchestration.cognitive_service import CognitiveService

logger = getLogger(__name__)


# ID: 87134386-7269-4628-a6fb-952bf6f2790e
class ContextAwareTestGenerator:
    """Generates tests using ContextPackage for richer context.

    Key improvements over SimpleTestGenerator:
    - Provides full symbol dependencies to LLM
    - Includes related test examples
    - Better success rate through context
    """

    def __init__(self, cognitive_service: CognitiveService) -> None:
        """Initialize with LLM and context services."""
        self.cognitive = cognitive_service
        self.context_service = ContextService(
            cognitive_service=cognitive_service,
            project_root=str(settings.REPO_PATH),
        )

    # ID: 4a5a573a-9c74-4048-adfb-0affde2d6aaa
    async def generate_test_for_symbol(
        self,
        file_path: str,
        symbol_name: str,
    ) -> dict[str, Any]:
        """Generate a test for ONE symbol with full context.

        Args:
            file_path: Path to source file (e.g., "src/core/foo.py")
            symbol_name: Name of function/class to test

        Returns:
            {
                "status": "success" | "skipped" | "failed",
                "test_code": str | None,
                "passed": bool,
                "reason": str
            }
        """
        try:
            # Extract symbol code
            symbol_code = self._extract_symbol_code(file_path, symbol_name)
            if not symbol_code:
                return {
                    "status": "skipped",
                    "test_code": None,
                    "passed": False,
                    "reason": f"Could not extract {symbol_name} from {file_path}",
                }

            # Build context package for this symbol
            context_packet = await self._build_context_for_symbol(
                file_path,
                symbol_name,
            )

            # Generate test with full context
            test_code = await self._generate_test_with_context(
                file_path=file_path,
                symbol_name=symbol_name,
                symbol_code=symbol_code,
                context_packet=context_packet,
            )

            if not test_code:
                return {
                    "status": "failed",
                    "test_code": None,
                    "passed": False,
                    "reason": "LLM did not return valid code",
                }

            # Validate the generated test
            passed, error = await self._try_run_test(test_code, symbol_name)

            if passed:
                return {
                    "status": "success",
                    "test_code": test_code,
                    "passed": True,
                    "reason": "Test compiled and passed",
                }

            return {
                "status": "failed",
                "test_code": test_code,
                "passed": False,
                "reason": f"Test failed: {error[:200]}",
            }

        except Exception as exc:  # noqa: BLE001
            logger.error("Error generating test for %s: %s", symbol_name, exc)
            return {
                "status": "failed",
                "test_code": None,
                "passed": False,
                "reason": str(exc),
            }

    async def _build_context_for_symbol(
        self,
        file_path: str,
        symbol_name: str,
    ) -> dict[str, Any]:
        """Build ContextPackage for a specific symbol."""
        task_spec: dict[str, Any] = {
            "task_id": f"test_gen_{symbol_name}",
            "task_type": "test.generate",
            "summary": f"Generate test for {symbol_name} in {file_path}",
            "roots": [file_path],
            "include": ["*.py"],
            "exclude": ["*test*", "*__pycache__*"],
            "max_tokens": 3000,  # Reasonable limit
            "max_items": 10,  # Related files/symbols
        }

        try:
            return await self.context_service.build_for_task(task_spec, use_cache=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to build context package: %s", exc)
            # Return minimal context - context is a list
            return {"context": []}

    async def _generate_test_with_context(
        self,
        file_path: str,
        symbol_name: str,
        symbol_code: str,
        context_packet: dict[str, Any],
    ) -> str | None:
        """Generate test code using ContextPackage information."""
        # Extract useful context - context is a list of items
        context_items = context_packet.get("context", [])

        # Build enriched prompt
        module_path = file_path.replace("src/", "").replace(".py", "").replace("/", ".")

        # Include related symbols/imports
        imports_section = ""
        if context_items:
            imports: set[str] = set()
            for item in context_items[:5]:  # Top 5 related items
                if item.get("item_type") == "symbol" and "path" in item:
                    # Extract module from path
                    item_path = item["path"].replace("src/", "").replace(".py", "")
                    module = item_path.replace("/", ".")
                    imports.add(module)
            if imports:
                imports_section = "\n\nRelated modules you may need:\n" + "\n".join(
                    f"- {imp}" for imp in sorted(imports)[:3]
                )

        prompt = f"""Generate a pytest test for this Python symbol from {file_path}.

```python
{symbol_code}
```

Module path: {module_path}{imports_section}

Requirements:
- Write ONE test function named: test_{symbol_name}
- Import like: from {module_path} import {symbol_name}
- Test the happy path (basic functionality)
- Use mocks if needed: from unittest.mock import MagicMock, AsyncMock, patch
- Keep it simple — roughly 5–15 lines
- Do NOT access real databases, HTTP services, or the filesystem directly
- Output ONLY the test function inside a ```python code block

Example format:

```python
def test_{symbol_name}():
    from {module_path} import {symbol_name}
    # Your test here
    result = {symbol_name}()
    assert result is not None
```"""

        try:
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(
                prompt,
                user_id="context_aware_test_gen",
            )
            # Use shared utility to extract python code from the response
            return extract_python_code_from_response(response)
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM request failed: %s", exc)
            return None

    def _extract_symbol_code(self, file_path: str, symbol_name: str) -> str | None:
        """Extract source code for a specific symbol using AST."""
        try:
            full_path = settings.REPO_PATH / file_path
            source = full_path.read_text(encoding="utf-8")
            lines = source.splitlines()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if (
                    isinstance(
                        node,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.ClassDef,
                        ),
                    )
                    and getattr(node, "name", None) == symbol_name
                ):
                    start = node.lineno - 1
                    end = node.end_lineno if hasattr(node, "end_lineno") else start + 20
                    return "\n".join(lines[start:end])

            return None
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Failed to extract %s from %s: %s", symbol_name, file_path, exc
            )
            return None

    async def _try_run_test(
        self,
        test_code: str,
        symbol_name: str,
    ) -> tuple[bool, str]:
        """Try to run the test. Return (passed, error_msg)."""
        temp_dir = settings.REPO_PATH / "work" / "testing" / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                dir=temp_dir,
                encoding="utf-8",
            ) as f:
                content = (
                    f"# Auto-generated test for {symbol_name}\n"
                    "import pytest\n"
                    "from unittest.mock import MagicMock, AsyncMock, patch\n\n"
                    f"{test_code}\n"
                )
                f.write(content)
                temp_path = f.name

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
                    proc.communicate(),
                    timeout=10.0,
                )
            except TimeoutError:
                proc.kill()
                return False, "Test timed out after 10 seconds"

            if proc.returncode == 0:
                return True, ""

            error = stderr.decode("utf-8", errors="replace") or stdout.decode(
                "utf-8",
                errors="replace",
            )
            return False, error

        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
        finally:
            if temp_path is not None:
                Path(temp_path).unlink(missing_ok=True)
