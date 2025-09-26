# src/system/admin/chat.py
"""
Implements the 'core-admin chat' command for conversational interaction.
"""

from __future__ import annotations

import json
import subprocess

import typer
from dotenv import load_dotenv

from core.agents.intent_translator import IntentTranslator
from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response

log = getLogger("core_admin.chat")
load_dotenv()


# ID: ab5e8f95-ba22-4845-9903-2aa02b618dd2
def chat(user_input: str = typer.Argument(..., help="Your goal in natural language.")):
    """
    Assesses your natural language goal and provides a clear, actionable command.
    """
    if not settings.LLM_ENABLED:
        log.error(
            "❌ The 'chat' command requires LLMs to be enabled in your .env file."
        )
        raise typer.Exit(code=1)

    log.info(f"Translating user goal: '{user_input}'")

    # --- This is the new, architecturally-aligned logic ---
    # It generates the help text, injects it via the pipeline, and uses the agent.
    try:
        # Generate the CLI help text to use as context
        help_text_result = subprocess.run(
            ["poetry", "run", "core-admin", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        help_text = help_text_result.stdout
        help_file = settings.REPO_PATH / "reports" / "cli_help.txt"
        help_file.parent.mkdir(exist_ok=True)
        help_file.write_text(help_text, encoding="utf-8")

        cognitive_service = CognitiveService(settings.REPO_PATH)
        translator = IntentTranslator(cognitive_service)
        response_text = translator.translate(user_input)

        response_json = extract_json_from_response(response_text)
        if not response_json:
            raise json.JSONDecodeError(
                "No valid JSON found in response.", response_text, 0
            )

        if "command" in response_json:
            command = response_json["command"]
            typer.secho("\n✅ AI Suggestion:", fg=typer.colors.GREEN)
            typer.echo("Here is the recommended command to achieve your goal:")
            typer.secho(f"\n  {command}\n", fg=typer.colors.CYAN)
        elif "error" in response_json:
            error_message = response_json["error"]
            typer.secho("\n⚠️ AI Assessment:", fg=typer.colors.YELLOW)
            typer.echo(error_message)
        else:
            raise KeyError("AI response missing 'command' or 'error' key.")

    except (json.JSONDecodeError, KeyError) as e:
        log.error(f"Failed to parse the AI's translation: {e}")
        typer.echo("The AI returned a response I couldn't understand. Raw response:")
        typer.echo(response_text)
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to generate CLI help text: {e.stderr}")
        raise typer.Exit(code=1)
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise typer.Exit(code=1)


# ID: 7989df2a-e653-4b38-afde-adaad2385482
def register(app: typer.Typer):
    """Register the 'chat' command with the main CLI app."""
    app.command("chat")(chat)
