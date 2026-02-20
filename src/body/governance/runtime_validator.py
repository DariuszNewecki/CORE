# src/body/governance/runtime_validator.py
# ID: 2b55693e-54fd-4e36-ab4c-29075a361014

"""
Runtime Validator - Body Layer Execution Service.

Provides the "Canary Sandbox" capability to run the project's test suite
against proposed code changes in a safe, isolated environment.

CONSTITUTIONAL ALIGNMENT (V2.3.0):
- Relocated: Moved from Mind to Body to resolve architecture.mind.no_body_invocation.
- Responsibility: Execution of sandboxed tests (Body capability).
- The Airlock: Subprocesses run with a SANITIZED environment to prevent
  leakage or corruption of production infrastructure.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from body.services.file_service import FileService
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: 282dad34-9366-49a0-91dd-c889a7d6f8da
class RuntimeValidatorService:
    """
    A service to test code changes in an isolated environment (Canary).

    CONSTITUTIONAL COMPLIANCE:
    - Resides in Body layer (Execution).
    - Uses FileService for all file operations.
    - Enforces Environment Isolation (The Airlock).
    """

    def __init__(self, path_resolver: PathResolver, test_timeout: int = 60):
        self._paths = path_resolver
        self.repo_root = self._paths.repo_root
        self.test_timeout = test_timeout

    # ID: 3615c13a-c101-4bca-9a10-7bb72604e13b
    async def run_tests_in_canary(
        self, file_path_str: str, new_code_content: str
    ) -> tuple[bool, str]:
        """
        Creates a temporary copy of the project, applies the new code, and runs pytest.
        Uses a SANITIZED environment to prevent side effects on the host system.

        Returns:
            A tuple of (passed: bool, details: str).
        """
        # Use a tmpdir for isolation.
        with tempfile.TemporaryDirectory(prefix="core_canary_") as tmpdir:
            canary_path = Path(tmpdir) / "canary_repo"
            logger.info("Creating canary test environment at %s...", canary_path)

            try:
                # 1. Initialize FileService rooted at the canary repo
                fs = FileService(canary_path)

                # 2. Replicate the Body (Code)
                fs.ensure_dir(".")
                _copy_repo_tree(
                    src_root=self.repo_root,
                    dst_root=canary_path,
                    file_service=fs,
                    ignore_names={
                        ".git",
                        self._paths.intent_root.name,  # Don't copy .intent/
                        ".venv",
                        "venv",
                        "__pycache__",
                        ".pytest_cache",
                        ".ruff_cache",
                        "work",
                        ".env",  # DANGER: Do not copy .env
                        ".env.test",  # DANGER: Do not copy .env.test
                    },
                )

                # 3. Apply the Candidate Code
                rel_target = Path(file_path_str).as_posix().lstrip("./")
                # Use get_file_handler() escape hatch to write the proposed code
                file_handler = fs.get_file_handler()
                file_handler.write_runtime_text(rel_target, new_code_content)

                # 4. Construct "The Airlock" (Sanitized Environment)
                safe_env = os.environ.copy()

                # Nuke keys to prevent sandbox leakage
                for unsafe in [
                    "DATABASE_URL",
                    "LLM_API_KEY",
                    "CORE_MASTER_KEY",
                    "QDRANT_URL",
                    "QDRANT_API_KEY",
                ]:
                    if unsafe in safe_env:
                        del safe_env[unsafe]

                # Inject Safe Defaults (Force Unit Test Mode)
                safe_env["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
                safe_env["CORE_ENV"] = "TEST"
                safe_env["LLM_ENABLED"] = "false"
                safe_env["PYTHONPATH"] = str(canary_path)

                logger.info("Running test suite in AIRLOCKED canary environment...")

                # 5. Execute
                proc = await asyncio.create_subprocess_exec(
                    "poetry",
                    "run",
                    "pytest",
                    cwd=canary_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=safe_env,
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


def _copy_repo_tree(
    src_root: Path, dst_root: Path, file_service: FileService, ignore_names: set[str]
) -> None:
    """
    Copy a repository tree via governed writes.
    """
    src_root = Path(src_root).resolve()
    # Walk the tree
    for src_path in src_root.rglob("*"):
        rel_parts = src_path.relative_to(src_root).parts
        if any(part in ignore_names for part in rel_parts):
            continue

        rel = src_path.relative_to(src_root).as_posix()

        if src_path.is_dir():
            file_service.ensure_dir(rel)
            continue

        if src_path.is_file():
            file_service.write_runtime_bytes(rel, src_path.read_bytes())
