# src/features/self_healing/simple_test_generator.py

"""
Ultra-simple test generator: one symbol at a time, keep what works.

CONSTITUTIONAL FIX:
- Isolates pre-flight execution using --rootdir and disabling cache providers.
- Prevents permission errors in sandboxed environments.
- Hardened prompt to prevent datetime-mocking logic errors.
"""

from __future__ import annotations

import ast
import asyncio
import datetime
import tempfile
from pathlib import Path
from typing import Any

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.utils.parsing import extract_python_code_from_response
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: 21623149-488d-43c8-9056-1bf255428dde
class SimpleTestGenerator:
    """Generates tests for individual symbols one at a time."""

    def __init__(
        self,
        cognitive_service: CognitiveService,
        file_handler: FileHandler,
        repo_root: Path,
    ) -> None:
        self.cognitive = cognitive_service
        self.file_handler = file_handler
        self.repo_root = repo_root

    # ID: cf4829fd-5d26-44f2-b5af-219528cd77c3
    async def generate_test_for_symbol(
        self, file_path: str, symbol_name: str
    ) -> dict[str, Any]:
        """Generate a test for ONE symbol and validate it in a sandbox."""
        try:
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

            return {
                "status": "failed",
                "test_code": test_code,
                "passed": False,
                "reason": f"Test failed validation: {error}",
            }

        except Exception as exc:
            logger.error("Error generating test for %s: %s", symbol_name, exc)
            return {
                "status": "failed",
                "test_code": None,
                "passed": False,
                "reason": str(exc),
            }

    def _extract_symbol_code(self, file_path: str, symbol_name: str) -> str | None:
        """Extract source code for a specific symbol using AST."""
        try:
            full_path = self.repo_root / file_path
            source = full_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if (
                    isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
                    and node.name == symbol_name
                ):
                    lines = source.splitlines()
                    start = node.lineno - 1
                    end = (
                        node.end_lineno
                        if hasattr(node, "end_lineno") and node.end_lineno
                        else start + 20
                    )
                    return "\n".join(lines[start:end])

            return None
        except Exception as exc:
            logger.debug(
                "Failed to extract %s from %s: %s", symbol_name, file_path, exc
            )
            return None

    async def _generate_test_code(
        self, file_path: str, symbol_name: str, symbol_code: str
    ) -> str | None:
        """Loads prompt from var/prompts/ and calls LLM."""
        rel_path = file_path.replace("src/", "", 1)
        module_path = rel_path.replace("/", ".").replace(".py", "")

        try:
            prompt_path = (
                self.repo_root / "var" / "prompts" / "accumulative_test_gen.txt"
            )
            template = prompt_path.read_text(encoding="utf-8")

            # STRENGTHENING: Append a warning about datetime mocking to the template
            final_prompt = template.format(
                file_path=file_path,
                symbol_code=symbol_code,
                module_path=module_path,
                symbol_name=symbol_name,
            )
            final_prompt += "\n\nCRITICAL: If you mock datetime, do NOT use the real datetime.now() for comparisons, as it will cause a multi-year delta."

            client = await self.cognitive.aget_client_for_role("Coder")
            response = await client.make_request_async(
                final_prompt, user_id="simple_test_gen"
            )
            return extract_python_code_from_response(response)
        except Exception as exc:
            logger.error("Failed to generate test code from prompt: %s", exc)
            return None

    async def _try_run_test(self, test_code: str, symbol_name: str) -> tuple[bool, str]:
        """Run the test in a fully isolated, config-less sandbox with explicit rootdir."""
        # Ensure directories exist via governed channel
        self.file_handler.ensure_dir("work/testing/failures")
        self.file_handler.ensure_dir("work/testing/temp")

        failures_dir = self.repo_root / "work" / "testing" / "failures"
        temp_dir = self.repo_root / "work" / "testing" / "temp"

        temp_path: str | None = None
        content = f"# Pre-flight test for {symbol_name}\n{test_code}\n"

        try:

            def _create_temp() -> str:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".py", delete=False, dir=temp_dir, encoding="utf-8"
                ) as f:
                    f.write(content)
                    return f.name

            temp_path = await asyncio.to_thread(_create_temp)
            src_path = str((self.repo_root / "src").resolve())

            # CONSTITUTIONAL SANDBOX:
            # -c /dev/null: ignores local pyproject.toml
            # --rootdir: prevents pytest from defaulting to /dev/ as root
            # -p no:cacheprovider: prevents permission errors creating .pytest_cache
            proc = await asyncio.create_subprocess_exec(
                "env",
                f"PYTHONPATH={src_path}",
                "poetry",
                "run",
                "pytest",
                "-c",
                "/dev/null",
                "--rootdir",
                str(self.repo_root),
                "-p",
                "no:cov",
                "-p",
                "no:cacheprovider",
                "-v",
                "--tb=short",
                temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_root),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=20.0
                )
            except TimeoutError:
                proc.kill()
                return False, "Test execution timed out (20s)"

            if proc.returncode == 0:
                return True, ""

            error = (
                stderr.decode("utf-8", errors="replace")
                + "\n"
                + stdout.decode("utf-8", errors="replace")
            )

            await asyncio.to_thread(self._save_failed_test, symbol_name, content, error)
            return False, error

        except Exception as exc:
            return False, str(exc)
        finally:
            if temp_path:
                await asyncio.to_thread(Path(temp_path).unlink, missing_ok=True)

    def _save_failed_test(self, symbol_name: str, test_code: str, error: str) -> None:
        """Sync helper for saving failed test artifacts via governed channel."""
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        test_file_rel = f"work/testing/failures/test_{symbol_name}_{ts}.py"
        error_file_rel = f"work/testing/failures/test_{symbol_name}_{ts}.error.txt"

        try:
            result = self.file_handler.write_runtime_text(test_file_rel, test_code)
            if result.status != "success":
                raise RuntimeError(f"Governance rejected write: {result.message}")

            result = self.file_handler.write_runtime_text(error_file_rel, error)
            if result.status != "success":
                raise RuntimeError(f"Governance rejected write: {result.message}")
        except Exception:
            pass
