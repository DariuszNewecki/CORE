# src/features/self_healing/clarity_service.py

"""
Implements the 'fix clarity' command, using an AI agent to perform
principled refactoring of Python code for improved readability and simplicity.
"""

import asyncio
from pathlib import Path

from rich.console import Console

from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


async def _async_fix_clarity(context: CoreContext, file_path: Path, dry_run: bool):
    """Async core logic for clarity-focused refactoring."""
    logger.info(f"🔬 Analyzing '{file_path.name}' for clarity improvements...")
    cognitive_service = context.cognitive_service

    prompt_template = (
        settings.MIND / "prompts" / "refactor_for_clarity.prompt"
    ).read_text()
    original_code = file_path.read_text("utf-8")

    final_prompt = prompt_template.replace("{source_code}", original_code)

    refactor_client = await cognitive_service.aget_client_for_role(
        "RefactoringArchitect"
    )
    with console.status(
        "[bold green]Asking AI Architect to refactor for clarity...[/bold green]"
    ):
        refactored_code = await refactor_client.make_request_async(
            final_prompt,
            user_id="clarity_fixer_agent",
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
    else:
        file_path.write_text(refactored_code, "utf-8")
        console.print(
            f"\n[bold green]✅ Successfully refactored '{file_path.name}' for clarity.[/bold green]"
        )


def fix_clarity(context: CoreContext, file_path: Path, dry_run: bool) -> None:
    """
    Public wrapper for clarity refactoring.

    Used by the self-healing CLI and tests. Executes the async implementation
    in a fresh event loop.
    """
    asyncio.run(_async_fix_clarity(context, file_path, dry_run))


def _fix_clarity(context: CoreContext, file_path: Path, dry_run: bool) -> None:
    """
    Backwards-compatible alias for older callers.

    Prefer using `fix_clarity` directly.
    """
    asyncio.run(_async_fix_clarity(context, file_path, dry_run))
