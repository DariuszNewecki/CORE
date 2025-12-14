# src/shared/utils/subprocess_utils.py

"""
Provides shared utilities for running external commands as subprocesses.
"""

from __future__ import annotations

import shutil
import subprocess

import typer
from rich.console import Console

from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: f555860f-aeb3-4a20-92ff-eee51b7f4501
def run_poetry_command(description: str, command: list[str]):
    """Helper to run a command via Poetry, log it, and handle errors."""
    POETRY_EXECUTABLE = shutil.which("poetry")
    if not POETRY_EXECUTABLE:
        logger.error("❌ Could not find 'poetry' executable in your PATH.")
        raise typer.Exit(code=1)
    typer.secho(f"\n{description}", bold=True)
    full_command = [POETRY_EXECUTABLE, "run", *command]
    try:
        result = subprocess.run(
            full_command, check=True, text=True, capture_output=True
        )
        if result.stdout:
            logger.info(result.stdout)
        if result.stderr:
            logger.info("[yellow]%s[/yellow]", result.stderr)
    except subprocess.CalledProcessError as e:
        logger.error("\n❌ Command failed: %s", " ".join(full_command))
        if e.stdout:
            logger.info(e.stdout)
        if e.stderr:
            logger.info("[bold red]%s[/bold red]", e.stderr)
        raise typer.Exit(code=1)
