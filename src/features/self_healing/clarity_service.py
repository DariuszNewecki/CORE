# src/system/admin/fixer_clarity.py
"""
Implements the 'fix clarity' command, using an AI agent to perform
principled refactoring of Python code for improved readability and simplicity.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.fixer_clarity")
console = Console()


async def _async_fix_clarity(file_path: Path, dry_run: bool):
    """Async core logic for clarity-focused refactoring."""
    log.info(f"🔬 Analyzing '{file_path.name}' for clarity improvements...")

    cognitive_service = CognitiveService(settings.REPO_PATH)
    prompt_template = (
        settings.MIND / "prompts" / "refactor_for_clarity.prompt"
    ).read_text()

    original_code = file_path.read_text("utf-8")
    final_prompt = prompt_template.replace("{source_code}", original_code)

    refactor_client = cognitive_service.get_client_for_role("RefactoringArchitect")

    with console.status(
        "[bold green]Asking AI Architect to refactor for clarity...[/bold green]"
    ):
        refactored_code = await refactor_client.make_request_async(
            final_prompt, user_id="clarity_fixer_agent"
        )

    if not refactored_code.strip() or refactored_code.strip() == original_code.strip():
        console.print(
            "[bold green]✅ AI Architect found no clarity improvements to make.[/bold green]"
        )
        return

    if dry_run:
        console.print(
            f"\n[bold yellow]-- DRY RUN: Would refactor {file_path.name} --[/bold yellow]"
        )
        # You can add a diff view here if desired in the future
    else:
        file_path.write_text(refactored_code, "utf-8")
        console.print(
            f"\n[bold green]✅ Successfully refactored '{file_path.name}' for clarity.[/bold green]"
        )


# ID: 90f74d6c-6ee1-4174-b231-1813d97b1562
def fix_clarity(
    file_path: Path = typer.Argument(
        ..., help="Path to the Python file to refactor.", exists=True, dir_okay=False
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the refactoring to the file."
    ),
):
    """Uses an AI agent to refactor a Python file for improved clarity and simplicity."""
    asyncio.run(_async_fix_clarity(file_path, dry_run=not write))
