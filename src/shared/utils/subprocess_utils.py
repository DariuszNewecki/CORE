# src/shared/utils/subprocess_utils.py

"""
Provides shared utilities for running external commands as subprocesses.
"""

from __future__ import annotations

import shutil
import subprocess

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 68adcb06-28c4-426c-8f9f-70a24f8f8ff7
class SubprocessCommandError(RuntimeError):
    """Raised when a subprocess command fails."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


# ID: f555860f-aeb3-4a20-92ff-eee51b7f4501
def run_poetry_command(description: str, command: list[str]):
    """Helper to run a command via Poetry, log it, and handle errors."""
    POETRY_EXECUTABLE = shutil.which("poetry")
    if not POETRY_EXECUTABLE:
        logger.error("❌ Could not find 'poetry' executable in your PATH.")
        raise SubprocessCommandError("poetry executable not found.", exit_code=1)

    logger.info(description)
    full_command = [POETRY_EXECUTABLE, "run", *command]
    try:
        result = subprocess.run(
            full_command, check=True, text=True, capture_output=True
        )
        if result.stdout:
            logger.info(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)
    except subprocess.CalledProcessError as e:
        logger.error("❌ Command failed: %s", " ".join(full_command))
        if e.stdout:
            logger.info(e.stdout)
        if e.stderr:
            logger.error(e.stderr)
        raise SubprocessCommandError("poetry command failed.", exit_code=1) from e
