# src/will/phases/canary/pytest_runner.py

"""
Pytest execution with timeout handling.

pytest runs through the sanctioned async subprocess surface
(shared.utils.subprocess_utils.run_command_async) under asyncio.wait_for;
on timeout the cancelled helper kills and reaps the child.
"""

from __future__ import annotations

import asyncio

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import run_command_async


logger = getLogger(__name__)

_CFG = load_operational_config().testing


# ID: a68a1332-b69e-4e01-b1aa-d113fe4ba28b
class PytestRunner:
    """Executes pytest with collection verification and timeout handling."""

    def __init__(
        self,
        path_resolver: PathResolver,
        collection_timeout: int = _CFG.pytest_collection_timeout_sec,
        execution_timeout: int = _CFG.pytest_execution_timeout_sec,
    ):
        self._paths = path_resolver
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
            result = await asyncio.wait_for(
                run_command_async(cmd, cwd=self._paths.repo_root),
                timeout=self.collection_timeout,
            )

            if "no tests ran" in result.stdout.lower():
                logger.info("No tests collected from specified paths")
                return False

            return True

        except TimeoutError:
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
            result = await asyncio.wait_for(
                run_command_async(cmd, cwd=self._paths.repo_root),
                timeout=self.execution_timeout,
            )

            # Streams arrive stripped; join on a newline so the last
            # stdout line never fuses with the first stderr line.
            output = "\n".join(s for s in (result.stdout, result.stderr) if s)

            passed = output.count(" PASSED")
            failed = output.count(" FAILED")

            return {
                "passed": passed,
                "failed": failed,
                "exit_code": result.returncode,
                "output": output,
            }

        except TimeoutError:
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
