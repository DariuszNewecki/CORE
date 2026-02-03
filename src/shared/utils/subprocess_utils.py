# src/shared/utils/subprocess_utils.py
"""
Provides shared utilities for running external commands as subprocesses.
Includes both sync and async variants to support the full CLI lifecycle.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from shared.exceptions import CoreError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: cfb6141b-6fe5-44c9-9819-cf2cab84d06d
class SubprocessCommandError(CoreError):
    """Raised when subprocess command execution fails."""


@dataclass
# ID: 6f1059a4-bacb-429d-b205-01eeb3cb38e1
class SubprocessResult:
    """Standardized result for async subprocess calls."""

    stdout: str
    stderr: str
    returncode: int


# ID: missing-async-helper-fixed
# ID: a83abb8d-b9c6-45f1-bf2c-e01b62420ebf
async def run_command_async(
    args: list[str], cwd: Path | str | None = None
) -> SubprocessResult:
    """
    Executes a shell command asynchronously.
    Required for non-blocking UI and Agent interactions.
    """
    logger.debug("Async Exec: %s", " ".join(args))

    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )

    stdout, stderr = await process.communicate()

    return SubprocessResult(
        stdout=stdout.decode().strip(),
        stderr=stderr.decode().strip(),
        returncode=process.returncode or 0,
    )


# ID: f555860f-aeb3-4a20-92ff-eee51b7f4501
def run_poetry_command(description: str, command: list[str]):
    """Helper to run a command via Poetry, log it, and handle errors (Synchronous)."""
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
