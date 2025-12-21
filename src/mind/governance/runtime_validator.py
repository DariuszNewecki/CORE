# src/mind/governance/runtime_validator.py

"""
Provides a service to run the project's test suite against proposed code changes
in a safe, isolated "canary" environment.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0cbf9038-fa70-4ea4-ae13-b478552f9d79
class RuntimeValidatorService:
    """A service to test code changes in an isolated environment."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.ignore_patterns = shutil.ignore_patterns(
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "work",
        )
        self.test_timeout = settings.model_extra.get("TEST_RUNNER_TIMEOUT", 60)

    # ID: 548eb332-6e28-4e75-a967-d499ad86fd2c
    async def run_tests_in_canary(
        self, file_path_str: str, new_code_content: str
    ) -> tuple[bool, str]:
        """
        Creates a temporary copy of the project, applies the new code, and runs pytest.

        Returns:
            A tuple of (passed: bool, details: str).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            canary_path = Path(tmpdir) / "canary_repo"
            logger.info("Creating canary test environment at %s...", canary_path)
            try:
                shutil.copytree(
                    self.repo_root, canary_path, ignore=self.ignore_patterns
                )
                target_file = canary_path / file_path_str
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(new_code_content, encoding="utf-8")
                logger.info("Running test suite in canary environment...")
                proc = await asyncio.create_subprocess_exec(
                    "poetry",
                    "run",
                    "pytest",
                    cwd=canary_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=self.test_timeout
                    )
                except TimeoutError:
                    proc.kill()
                    logger.error("Canary tests timed out.")
                    return (
                        False,
                        f"Tests timed out after {self.test_timeout} seconds.",
                    )
                if proc.returncode == 0:
                    logger.info("✅ Canary tests PASSED.")
                    return (True, "All tests passed in the isolated environment.")
                else:
                    logger.warning("❌ Canary tests FAILED.")
                    error_details = f"Pytest failed with exit code {proc.returncode}.\n\nSTDOUT:\n{stdout.decode()}\n\nSTDERR:\n{stderr.decode()}"
                    return (False, error_details)
            except Exception as e:
                logger.error("Error during canary test run: %s", e, exc_info=True)
                return (False, f"An unexpected exception occurred: {e!s}")
