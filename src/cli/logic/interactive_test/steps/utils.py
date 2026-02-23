# src/body/cli/logic/interactive_test/steps/utils.py

"""Refactored logic for src/body/cli/logic/interactive_test/steps/utils.py."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f2849148-1931-4e9b-b5ff-84daeecb6061
async def open_in_editor_async(file_path: Path) -> bool:
    """Open a file in the user's editor asynchronously."""
    editor = os.environ.get("EDITOR", "nano")
    try:
        process = await asyncio.create_subprocess_exec(
            editor,
            str(file_path),
            stdin=asyncio.subprocess.DEVNULL,
        )
        returncode = await process.wait()
        return returncode == 0
    except Exception as e:
        logger.error("Failed to open editor: %s", e)
        return False
