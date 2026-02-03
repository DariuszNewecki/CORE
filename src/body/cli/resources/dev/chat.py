# src/body/cli/resources/dev/chat.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

"""
AI-assisted CLI command translation.
Resource-First implementation for 'core-admin dev chat'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from body.services.file_service import FileService
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response
from shared.utils.subprocess_utils import run_command_async
from will.agents.intent_translator import IntentTranslator
from will.orchestration.cognitive_service import CognitiveService

from . import app


logger = getLogger(__name__)
console = Console()

# --- Internal Helpers (Moved from deleted API layer) ---


async def _require_llm_enabled(session) -> None:
    """Fails fast if LLMs are not enabled."""
    config = await ConfigService.create(session)
    llm_enabled = await config.get_bool("LLM_ENABLED", default=False)
    if not llm_enabled:
        console.print(
            "[red]Error: The 'chat' command requires LLMs to be enabled in the database.[/red]"
        )
        raise typer.Exit(code=1)


async def _get_cli_context_help(repo_path: Path) -> str:
    """Retrieves help text for a standard command to give the AI context."""
    args = ["poetry", "run", "core-admin", "check", "audit", "--help"]
    result = await run_command_async(args, cwd=repo_path)
    return result.stdout or ""


# --- The Command ---


@app.command("chat")
@core_command(dangerous=False, requires_context=True)
# ID: 9a55bda4-14c5-4867-a528-8acd275e9b75
async def chat_command(
    ctx: typer.Context,
    user_input: str = typer.Argument(..., help="Your goal in natural language."),
) -> None:
    """
    Assess a natural language goal and return an actionable CLI command.

    Example:
        core-admin dev chat "I want to synchronize the database and the code"
    """
    core_context: CoreContext = ctx.obj
    repo_path = core_context.git_service.repo_path

    # 1. Verification
    async with core_context.registry.session() as session:
        await _require_llm_enabled(session)

    console.print(f"[bold cyan]🤖 Thinking about:[/bold cyan] '{user_input}'...")

    try:
        # 2. Context Gathering
        help_text = await _get_cli_context_help(repo_path)

        # 3. Persistence (Body Layer via FileService)
        file_service = FileService(repo_path)
        await file_service.write_report("cli_help_context.txt", help_text)

        # 4. Cognitive Processing (Will Layer)
        # Re-initialize cognitive service for the translator
        cognitive_service = CognitiveService(repo_path)
        async with core_context.registry.session() as session:
            await cognitive_service.initialize(session)

        translator = IntentTranslator(cognitive_service, core_context.path_resolver)

        # Translate
        response_text = await translator.translate(user_input)
        response_json: dict[str, Any] | None = extract_json_from_response(response_text)

        if not response_json:
            console.print(
                "[red]The AI returned a response that could not be parsed as JSON.[/red]"
            )
            console.print(f"[dim]{response_text}[/dim]")
            return

        # 5. Presentation
        command = response_json.get("command")
        assessment = response_json.get("assessment") or response_json.get("error")

        if command:
            console.print("\n[bold green]💡 AI Suggestion:[/bold green]")
            console.print(
                f"Recommended command:\n\n  [bold cyan]{command}[/bold cyan]\n"
            )
        elif assessment:
            console.print("\n[bold yellow]🧐 AI Assessment:[/bold yellow]")
            console.print(f"{assessment}\n")
        else:
            console.print(
                "[red]AI response missing expected keys ('command' or 'assessment').[/red]"
            )

    except Exception as e:
        logger.exception("Chat logic failure")
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        raise typer.Exit(code=1)
