# src/will/cli_logic/chat.py

"""Provides functionality for the chat module."""

from __future__ import annotations

import asyncio
import json
import subprocess

import typer
from dotenv import load_dotenv

from services.config_service import config_service
from shared.config import settings
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response
from will.agents.intent_translator import IntentTranslator
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
load_dotenv()


# ID: 034f20de-56bb-4b25-aa48-d68a21de43cd
async def chat(
    user_input: str = typer.Argument(..., help="Your goal in natural language."),
):
    """
    Assesses your natural language goal and provides a clear, actionable command.
    """
    llm_enabled = await config_service.get_bool("LLM_ENABLED", default=False)
    if not llm_enabled:
        logger.error(
            "❌ The 'chat' command requires LLMs to be enabled. Check 'LLM_ENABLED' in the database."
        )
        raise typer.Exit(code=1)
    logger.info("Translating user goal: '%s'", user_input)
    try:
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
        response_text = await asyncio.to_thread(translator.translate, user_input)
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
        logger.error("Failed to parse the AI's translation: %s", e)
        typer.echo("The AI returned a response I couldn't understand. Raw response:")
        typer.echo(response_text)
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate CLI help text: {e.stderr}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise typer.Exit(code=1)
