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

log = getLogger("subprocess_utils")
console = Console()


# ID: 71034daa-0b93-4c24-910b-d1413b470795
def run_poetry_command(description: str, command: list[str]):
    """Helper to run a command via Poetry, log it, and handle errors."""
    POETRY_EXECUTABLE = shutil.which("poetry")
    if not POETRY_EXECUTABLE:
        log.error("❌ Could not find 'poetry' executable in your PATH.")
        raise typer.Exit(code=1)

    typer.secho(f"\n{description}", bold=True)
    full_command = [POETRY_EXECUTABLE, "run", *command]
    try:
        result = subprocess.run(
            full_command, check=True, text=True, capture_output=True
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[yellow]{result.stderr}[/yellow]")
    except subprocess.CalledProcessError as e:
        log.error(f"\n❌ Command failed: {' '.join(full_command)}")
        if e.stdout:
            console.print(e.stdout)
        if e.stderr:
            console.print(f"[bold red]{e.stderr}[/bold red]")
        raise typer.Exit(code=1)
