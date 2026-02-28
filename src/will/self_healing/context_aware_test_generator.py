# src/will/self_healing/context_aware_test_generator.py

"""Context-aware test generator using ContextPackage for better results.

This improves on SimpleTestGenerator by providing the LLM with richer context.
Enforces non-blocking I/O to satisfy the Async-Native architectural contract.
Complies with Body Contracts by avoiding direct os.environ access.
"""

from __future__ import annotations

import ast
import asyncio
import datetime
import tempfile
from pathlib import Path
from typing import Any

from body.services.file_service import FileService
from body.services.service_registry import service_registry
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 87134386-7269-4628-a6fb-952bf6f2790e
class ContextAwareTestGenerator:
    """Generates tests using ContextPackage for richer context."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        file_handler: FileService,
        repo_root: Path,
    ) -> None:
        """Initialize with LLM service and governed file operations."""
        self.cognitive = cognitive_service
        self.file_handler = file_handler
        self.repo_root = repo_root

    # ID: 4a5a573a-9c74-4048-adfb-0affde2d6aaa
    async def generate_test_for_symbol(
        self, file_path: str, symbol_name: str
    ) -> dict[str, Any]:
        """Generate a test for ONE symbol with full context."""
        try:
            from shared.infrastructure.context.service import ContextService

            context_service = ContextService(
                cognitive_service=self.cognitive,
                project_root=str(self.repo_root),
                session_factory=service_registry.session,
            )

            # AST + file I/O offloaded for async-native compliance
            symbol_code = await asyncio.to_thread(
                self._extract_symbol_code, file_path, symbol_name
            )
            if not symbol_code:
                return {
                    "status": "skipped",
                    "test_code": None,
                    "passed": False,
                    "reason": f"Could not extract {symbol_name} from {file_path}",
                }

            context_packet = await context_service.build_for_task(
                {
                    "task_id": f"test_gen_{symbol_name}",
                    "task_type": "test.generate",
                    "summary": f"Generate test for {symbol_name} in {file_path}",
                    "target_file": file_path,
                    "target_symbol": symbol_name,
                    "scope": {"traversal_depth": 1},
                },
                use_cache=True,
            )

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

            passed, error = await self._try_run_test(test_code, symbol_name, file_path)

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
                "reason": f"Test failed: {error}",
            }

        except Exception as exc:
            logger.error("Error generating test for %s: %s", symbol_name, exc)
            return {
                "status": "failed",
                "test_code": None,
                "passed": False,
                "reason": str(exc),
            }

    async def _generate_test_with_context(
        self,
        file_path: str,
        symbol_name: str,
        symbol_code: str,
        context_packet: dict[str, Any],
    ) -> str | None:
        """Generate test code using ContextPackage information."""
        module_path = (
            file_path.replace("src/", "", 1).replace(".py", "").replace("/", ".")
        )

        prompt = (
            f"Generate a pytest test for this Python symbol from {file_path}.\n"
            "```python\n"
            f"{symbol_code}\n"
            "```\n"
            f"Module path: {module_path}\n"
            "Requirements:\n"
            f"Write ONE test function named: test_{symbol_name}\n"
            f"Import like: from {module_path} import {symbol_name}\n"
            "Test the happy path (basic functionality)\n"
            "Use mocks for external I/O or DB\n"
            "Output ONLY the test function inside a ```python code block\n"
        )

        try:
            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(prompt, user_id="ctx_test_gen")
            return extract_python_code_from_response(response)
        except Exception as exc:
            logger.error("LLM request failed: %s", exc)
            return None

    def _extract_symbol_code(self, file_path: str, symbol_name: str) -> str | None:
        """Extract source code for a specific symbol using AST."""
        try:
            full_path = self.repo_root / file_path
            source = full_path.read_text(encoding="utf-8")
            lines = source.splitlines()

            tree = ast.parse(source)
            for node in ast.walk(tree):
                if (
                    isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
                    and node.name == symbol_name
                ):
                    start = node.lineno - 1
                    end = (
                        node.end_lineno
                        if hasattr(node, "end_lineno") and node.end_lineno
                        else start + 10
                    )
                    return "\n".join(lines[start:end])

            return None
        except Exception as exc:
            logger.debug("Failed to extract %s: %s", symbol_name, exc)
            return None

    async def _try_run_test(
        self, test_code: str, symbol_name: str, source_file: str
    ) -> tuple[bool, str]:
        """Try to run the test without direct os.environ access."""
        # Ensure directories exist via governed channel
        self.file_handler.ensure_dir("work/testing/failures")
        self.file_handler.ensure_dir("work/testing/temp")

        failures_dir = self.repo_root / "work" / "testing" / "failures"
        temp_dir = self.repo_root / "work" / "testing" / "temp"

        temp_path: str | None = None
        content = (
            f"# Auto-generated test for {symbol_name} from {source_file}\n"
            "import pytest\n"
            "from unittest.mock import MagicMock, AsyncMock, patch\n\n"
            f"{test_code}\n"
        )

        try:

            def _create_temp() -> str:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".py",
                    delete=False,
                    dir=temp_dir,
                    encoding="utf-8",
                ) as f:
                    f.write(content)
                    return f.name

            temp_path = await asyncio.to_thread(_create_temp)
            src_path = str((self.repo_root / "src").resolve())

            proc = await asyncio.create_subprocess_exec(
                "env",
                f"PYTHONPATH={src_path}",
                "poetry",
                "run",
                "pytest",
                temp_path,
                "-v",
                "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=15.0
                )
            except TimeoutError:
                proc.kill()
                msg = "Test timed out after 15 seconds"
                await asyncio.to_thread(
                    self._save_failed_test, symbol_name, content, msg
                )
                return False, msg

            if proc.returncode == 0:
                return True, ""

            full_error = (
                stderr.decode("utf-8", errors="replace")
                + "\n"
                + stdout.decode("utf-8", errors="replace")
            )
            await asyncio.to_thread(
                self._save_failed_test, symbol_name, content, full_error
            )
            return False, full_error

        except Exception as exc:
            error_msg = str(exc)
            if temp_path:
                try:
                    file_content = await asyncio.to_thread(
                        Path(temp_path).read_text, encoding="utf-8"
                    )
                    await asyncio.to_thread(
                        self._save_failed_test,
                        symbol_name,
                        file_content,
                        error_msg,
                    )
                except Exception:
                    await asyncio.to_thread(
                        self._save_failed_test,
                        symbol_name,
                        content,
                        error_msg,
                    )
            return False, error_msg
        finally:
            if temp_path:
                await asyncio.to_thread(Path(temp_path).unlink, missing_ok=True)

    def _save_failed_test(self, symbol_name: str, test_code: str, error: str) -> None:
        """Sync helper for saving artifacts via governed channel."""
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        test_file_rel = f"work/testing/failures/test_{symbol_name}_{ts}.py"
        error_file_rel = f"work/testing/failures/test_{symbol_name}_{ts}.error.txt"

        try:
            result = self.file_handler.write_runtime_text(test_file_rel, test_code)
            if result.status != "success":
                raise RuntimeError(f"Governance rejected write: {result.message}")

            result = self.file_handler.write_runtime_text(error_file_rel, error)
            if result.status != "success":
                raise RuntimeError(f"Governance rejected write: {result.message}")
        except Exception as exc:
            logger.warning("Failed to save artifacts: %s", exc)
