# src/cli/resources/dev/chat.py
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
from body.services.service_registry import _ServiceLoader
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response
from shared.utils.subprocess_utils import run_command_async

from .hub import app


logger = getLogger(__name__)
console = Console()


async def _require_llm_enabled(session) -> None:
    """Fails fast if LLMs are not enabled."""
    config = await ConfigService.create(session)
    llm_enabled = await config.get_bool("LLM_ENABLED", default=False)
    if not llm_enabled:
        logger.info(
            "[red]Error: The 'chat' command requires LLMs to be enabled in the database.[/red]"
        )
        raise typer.Exit(code=1)


async def _get_cli_context_help(repo_path: Path) -> str:
    """Retrieves help text for a standard command to give the AI context."""
    args = ["poetry", "run", "core-admin", "--help"]
    result = await run_command_async(args, cwd=repo_path)
    return result.stdout or ""


@app.command("chat")
@core_command(dangerous=False, requires_context=True)
# ID: d7627d21-9234-4499-925d-fa36eb7c2188
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
    async with core_context.registry.session() as session:
        await _require_llm_enabled(session)
    logger.info("[bold cyan]🤖 Thinking about:[/bold cyan] '%s'...", user_input)
    try:
        help_text = await _get_cli_context_help(repo_path)
        file_service = FileService(repo_path)
        await file_service.write_report("cli_help_context.txt", help_text)
        cognitive_service = await core_context.registry.get_cognitive_service()
        IntentTranslator = _ServiceLoader.import_class(
            "will.agents.intent_translator.IntentTranslator"
        )
        translator = IntentTranslator(cognitive_service, core_context.path_resolver)
        response_text = await translator.translate(user_input)
        response_json: dict[str, Any] | None = extract_json_from_response(response_text)
        if not response_json:
            logger.info(
                "[red]The AI returned a response that could not be parsed as JSON.[/red]"
            )
            logger.info("[dim]%s[/dim]", response_text)
            return
        command = response_json.get("command")
        assessment = response_json.get("assessment") or response_json.get("error")
        if command:
            logger.info("\n[bold green]💡 AI Suggestion:[/bold green]")
            logger.info(
                "Recommended command:\n\n  [bold cyan]%s[/bold cyan]\n", command
            )
        elif assessment:
            logger.info("\n[bold yellow]🧐 AI Assessment:[/bold yellow]")
            logger.info("%s\n", assessment)
        else:
            logger.info(
                "[red]AI response missing expected keys ('command' or 'assessment').[/red]"
            )
    except Exception as e:
        logger.exception("Chat logic failure")
        logger.info("[red]❌ Unexpected error: %s[/red]", e)
        raise typer.Exit(code=1)
