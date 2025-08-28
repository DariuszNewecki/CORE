# src/system/admin/chat.py
"""
Implements the 'core-admin chat' command for conversational interaction.
"""
from __future__ import annotations

import asyncio

import typer
from dotenv import load_dotenv

from agents.development_cycle import run_development_cycle
from agents.intent_translator import IntentTranslator
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.chat")
load_dotenv()


# CAPABILITY: conversational_interface
def chat(user_input: str = typer.Argument(..., help="Your goal in natural language.")):
    """
    Translates your natural language goal into a structured plan and executes it.
    """
    if not settings.LLM_ENABLED:
        log.error(
            "❌ The 'chat' command requires LLMs to be enabled in your .env file."
        )
        raise typer.Exit(code=1)

    log.info(f"Received user input via chat: '{user_input}'")

    # Step 1: Instantiate the services and the translator agent.
    cognitive_service = CognitiveService(settings.REPO_PATH)
    translator = IntentTranslator(cognitive_service)

    # Step 2: Use the translator to convert natural language to a structured goal.
    structured_goal = translator.translate(user_input)

    if not structured_goal or "Error:" in structured_goal:
        log.error(
            f"❌ Failed to translate the user's intent. AI response: {structured_goal}"
        )
        raise typer.Exit(code=1)

    typer.secho("\n🧠 Structured Goal:", bold=True)
    typer.secho(f"{structured_goal}", fg=typer.colors.CYAN)

    if not typer.confirm("\nDo you want to proceed with executing this goal?"):
        log.warning("Execution cancelled by user.")
        raise typer.Exit()

    # Step 3: Pass the structured goal to the existing development cycle.
    success, message = asyncio.run(run_development_cycle(structured_goal))

    # Step 4: Report the final outcome.
    if success:
        typer.secho("\n✅ Goal achieved successfully.", fg=typer.colors.GREEN)
        typer.secho(f"   -> {message}", fg=typer.colors.GREEN)
    else:
        typer.secho("\n❌ Goal execution failed.", fg=typer.colors.RED)
        typer.secho(f"   -> {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def register(app: typer.Typer):
    """Register the 'chat' command with the main CLI app."""
    app.command("chat")(chat)
