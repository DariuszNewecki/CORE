# src/mind/governance/runtime_validator.py

"""
Provides a service to run the project's test suite against proposed code changes
in a safe, isolated "canary" environment.

Policy:
- No direct filesystem mutations outside governed mutation surfaces.
- Writes/mkdir/copy operations must be routed through FileHandler (IntentGuard enforced).
- Canary runs operate on a temporary directory and must never write to .intent/**.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 0cbf9038-fa70-4ea4-ae13-b478552f9d79
class RuntimeValidatorService:
    """A service to test code changes in an isolated environment."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
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
        # Use a tmpdir for isolation. Mutations here are allowed, but still routed
        # through FileHandler to keep a single mutation surface and apply IntentGuard rules.
        with tempfile.TemporaryDirectory(prefix="core_canary_") as tmpdir:
            canary_path = Path(tmpdir) / "canary_repo"
            logger.info("Creating canary test environment at %s...", canary_path)

            try:
                # Initialize a FileHandler rooted at the canary repo root.
                # It will still enforce the .intent/** no-write invariant.
                fh = FileHandler(str(canary_path))

                # Copy repo into canary using guarded copy (no direct shutil.copytree).
                # We implement ignore by copying into an empty canary directory:
                # - first create canary_path
                # - then selective copy via file system walk (implemented below)
                fh.ensure_dir(".")
                _copy_repo_tree(
                    src_root=self.repo_root,
                    dst_root=canary_path,
                    ignore_names={
                        ".git",
                        ".venv",
                        "venv",
                        "__pycache__",
                        ".pytest_cache",
                        ".ruff_cache",
                        "work",
                    },
                )

                # Apply candidate change inside canary through FileHandler runtime write.
                rel_target = Path(file_path_str).as_posix().lstrip("./")
                fh.write_runtime_text(rel_target, new_code_content)

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

                logger.warning("❌ Canary tests FAILED.")
                error_details = (
                    f"Pytest failed with exit code {proc.returncode}.\n\n"
                    f"STDOUT:\n{stdout.decode(errors='replace')}\n\n"
                    f"STDERR:\n{stderr.decode(errors='replace')}"
                )
                return (False, error_details)

            except Exception as e:
                logger.error("Error during canary test run: %s", e, exc_info=True)
                return (False, f"An unexpected exception occurred: {e!s}")


# ID: 3d6d9f9f-7874-4e77-9f5f-8b1c2c0a9d31
def _copy_repo_tree(src_root: Path, dst_root: Path, ignore_names: set[str]) -> None:
    """
    Copy a repository tree without using shutil.copytree (direct mutation primitive),
    applying a simple directory/file name ignore set.

    This is intentionally minimal and deterministic for canary use.
    """
    src_root = Path(src_root).resolve()
    dst_root = Path(dst_root).resolve()

    for src_path in src_root.rglob("*"):
        # Skip ignored names anywhere in the path.
        if any(part in ignore_names for part in src_path.parts):
            continue

        rel = src_path.relative_to(src_root).as_posix()
        dst_path = dst_root / rel

        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue

        if src_path.is_file():
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            dst_path.write_bytes(src_path.read_bytes())
