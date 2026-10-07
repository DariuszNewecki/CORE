# src/cli/logic/interactive_test/steps/utils.py

"""Refactored logic for src/body/cli/logic/interactive_test/steps/utils.py."""

from __future__ import annotations

import os
from pathlib import Path

from shared.logger import getLogger
from shared.utils.subprocess_utils import run_child_process


logger = getLogger(__name__)


# ID: f2849148-1931-4e9b-b5ff-84daeecb6061
async def open_in_editor_async(file_path: Path) -> bool:
    """Open a file in the user's editor asynchronously.

    The editor inherits the terminal's stdio (including stdin) so it can be
    used interactively, and the caller's full environment.
    """
    editor = os.environ.get("EDITOR", "nano")
    try:
        returncode = await run_child_process(
            [editor, str(file_path)], cwd=Path.cwd(), env=dict(os.environ)
        )
        return returncode == 0
    except Exception as e:
        logger.error("Failed to open editor: %s", e)
        return False
