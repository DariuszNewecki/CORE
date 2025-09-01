# src/system/admin/chat.py
"""
Implements the 'core-admin chat' command for conversational interaction.
"""

from __future__ import annotations

import json

import typer
from dotenv import load_dotenv

from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.chat")
load_dotenv()


# CAPABILITY: conversational_interface
def chat(user_input: str = typer.Argument(..., help="Your goal in natural language.")):
    """
    Assesses your natural language goal and provides a clear, actionable command.
    """
    if not settings.LLM_ENABLED:
        log.error(
            "❌ The 'chat' command requires LLMs to be enabled in your .env file."
        )
        raise typer.Exit(code=1)

    log.info(f"Assessing user goal: '{user_input}'")

    # --- This is the new "Triage" logic ---
    cognitive_service = CognitiveService(settings.REPO_PATH)
    prompt_pipeline = PromptPipeline(settings.REPO_PATH)

    prompt_path = settings.MIND / "prompts" / "goal_assessor.prompt"
    if not prompt_path.exists():
        log.error(f"❌ Constitutional prompt not found at: {prompt_path}")
        raise typer.Exit(code=1)

    prompt_template = prompt_path.read_text(encoding="utf-8")
    final_prompt = prompt_pipeline.process(
        prompt_template.format(user_input=user_input)
    )

    # Use a strong reasoning model for this assessment
    assessor_client = cognitive_service.get_client_for_role("Planner")
    response_text = assessor_client.make_request(final_prompt, user_id="goal_assessor")

    try:
        assessment = json.loads(response_text)
        status = assessment.get("status")

        if status == "clear":
            goal = assessment.get("goal")
            typer.secho(
                "\n✅ Your goal is clear and actionable.", fg=typer.colors.GREEN
            )
            typer.echo("You can now run the 'develop' command with this goal:")
            typer.secho(
                f'\npoetry run core-admin develop "{goal}"\n', fg=typer.colors.CYAN
            )

        elif status == "vague":
            suggestion = assessment.get("suggestion")
            typer.secho("\n⚠️ Your goal is a bit vague.", fg=typer.colors.YELLOW)
            typer.echo(suggestion)
        else:
            log.error(f"AI returned an unexpected status: {status}")

    except (json.JSONDecodeError, KeyError):
        log.error("Failed to parse the AI's assessment. The raw response was:")
        typer.echo(response_text)
        raise typer.Exit(code=1)


# CAPABILITY: system.cli.register_chat_command
def register(app: typer.Typer):
    """Register the 'chat' command with the main CLI app."""
    app.command("chat")(chat)
