# src/will/phases/canary/pytest_runner.py

"""
Pytest execution with timeout handling.
"""

from __future__ import annotations

import asyncio

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a68a1332-b69e-4e01-b1aa-d113fe4ba28b
class PytestRunner:
    """Executes pytest with collection verification and timeout handling."""

    def __init__(self, collection_timeout: int = 30, execution_timeout: int = 300):
        self.collection_timeout = collection_timeout
        self.execution_timeout = execution_timeout

    # ID: c09109f2-9052-4b20-b2b8-f3f04e027832
    async def run_tests(self, test_paths: list[str]) -> dict:
        """
        Run pytest on specified test files.

        Returns dict with:
        - passed: number of passed tests
        - failed: number of failed tests
        - exit_code: pytest exit code (0 = success)
        - output: pytest output
        """
        # Verify tests can be collected
        can_collect = await self._verify_collection(test_paths)
        if not can_collect:
            return {
                "passed": 0,
                "failed": 0,
                "exit_code": 0,
                "output": "No tests collected",
            }

        # Execute tests
        return await self._execute_tests(test_paths)

    async def _verify_collection(self, test_paths: list[str]) -> bool:
        """Verify that pytest can collect tests from the specified paths."""
        cmd = [
            "pytest",
            "-v",
            "--tb=short",
            "--no-header",
            "--co",  # Collect only
            *test_paths,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(settings.REPO_PATH),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self.collection_timeout
            )

            output = stdout.decode(errors="replace")
            if "no tests ran" in output.lower():
                logger.info("No tests collected from specified paths")
                return False

            return True

        except TimeoutError:
            if proc.returncode is None:
                proc.kill()
            logger.warning(
                "Test collection timed out after %ds", self.collection_timeout
            )
            return False

        except Exception as e:
            logger.warning("Test collection check failed: %s", e)
            return False

    async def _execute_tests(self, test_paths: list[str]) -> dict:
        """Execute pytest and return results."""
        cmd = [
            "pytest",
            "-v",
            "--tb=short",
            "--no-header",
            "-x",  # Stop on first failure
            *test_paths,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(settings.REPO_PATH),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self.execution_timeout
            )

            output = stdout_bytes.decode(errors="replace") + stderr_bytes.decode(
                errors="replace"
            )

            passed = output.count(" PASSED")
            failed = output.count(" FAILED")

            return {
                "passed": passed,
                "failed": failed,
                "exit_code": proc.returncode or 0,
                "output": output,
            }

        except TimeoutError:
            if proc.returncode is None:
                proc.kill()
            logger.error("Tests timed out after %ds", self.execution_timeout)
            return {
                "passed": 0,
                "failed": 1,
                "exit_code": 124,  # Standard timeout exit code
                "output": f"Tests timed out after {self.execution_timeout} seconds",
            }

        except Exception as e:
            logger.error("Failed to run pytest: %s", e)
            return {
                "passed": 0,
                "failed": 1,
                "exit_code": 1,
                "output": str(e),
            }
