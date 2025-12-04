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


# ID: 1bb2303c-98bf-4f96-84c4-99ce75c8f044
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
            logger.info(f"[yellow]{result.stderr}[/yellow]")
    except subprocess.CalledProcessError as e:
        logger.error(f"\n❌ Command failed: {' '.join(full_command)}")
        if e.stdout:
            logger.info(e.stdout)
        if e.stderr:
            logger.info(f"[bold red]{e.stderr}[/bold red]")
        raise typer.Exit(code=1)
