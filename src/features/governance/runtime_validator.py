# src/features/governance/runtime_validator.py
"""
Provides a service to run the project's test suite against proposed code changes
in a safe, isolated "canary" environment.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from rich.console import Console

from shared.logger import getLogger

log = getLogger("runtime_validator")
console = Console()


# ID: c1a2b3d4-e5f6-7a8b-9c0d-1f2a3b4c5d6e
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

    # ID: d2b3c4d5-e6f7-a8b9-c0d1-e2f3a4b5c6d7
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
            log.info(f"Creating canary test environment at {canary_path}...")

            try:
                # 1. Create the isolated environment
                shutil.copytree(
                    self.repo_root, canary_path, ignore=self.ignore_patterns
                )

                # 2. Apply the proposed change
                target_file = canary_path / file_path_str
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(new_code_content, encoding="utf-8")

                # 3. Run the test suite inside the canary environment
                log.info("Running test suite in canary environment...")
                proc = await asyncio.create_subprocess_exec(
                    "poetry",
                    "run",
                    "pytest",
                    cwd=canary_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()

                if proc.returncode == 0:
                    log.info("✅ Canary tests PASSED.")
                    return True, "All tests passed in the isolated environment."
                else:
                    log.warning("❌ Canary tests FAILED.")
                    error_details = (
                        f"Pytest failed with exit code {proc.returncode}.\n\n"
                        f"STDOUT:\n{stdout.decode()}\n\n"
                        f"STDERR:\n{stderr.decode()}"
                    )
                    return False, error_details

            except Exception as e:
                log.error(f"Error during canary test run: {e}", exc_info=True)
                return False, f"An unexpected exception occurred: {str(e)}"
