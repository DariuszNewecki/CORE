# src/will/cli_logic/chat.py
# ID: cli.logic.chat
"""
Provides functionality for the chat module.
Refactored to comply with Constitutional Agent I/O policies.
"""

from __future__ import annotations

import asyncio
import json

import typer
from dotenv import load_dotenv

from shared.config import settings
from shared.infrastructure.config_service import config_service
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response
from shared.utils.subprocess_utils import run_command_async
from will.agents.intent_translator import IntentTranslator
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
load_dotenv()


# ID: e28b1579-1e68-40e2-9583-6774d0e8e48f
async def chat(
    user_input: str = typer.Argument(..., help="Your goal in natural language."),
) -> None:
    """
    Assesses your natural language goal and provides a clear, actionable command.
    """
    # 1. Constitutional Check: Is LLM enabled?
    llm_enabled = await config_service.get_bool("LLM_ENABLED", default=False)
    if not llm_enabled:
        logger.error(
            "❌ The 'chat' command requires LLMs to be enabled. Check 'LLM_ENABLED' in the database."
        )
        raise typer.Exit(code=1)

    logger.info("Translating user goal: '%s'", user_input)

    try:
        # 2. Generate Context (CLI Help) via Safe Subprocess Wrapper
        # We delegate execution to shared utils to satisfy security policy
        help_text_result = await run_command_async(
            ["poetry", "run", "core-admin", "--help"], cwd=settings.REPO_PATH
        )

        if help_text_result.returncode != 0:
            logger.error(
                "Failed to generate CLI help text: %s", help_text_result.stderr
            )
            raise typer.Exit(code=1)

        help_text = help_text_result.stdout

        # 3. Persist Context via Infrastructure Layer (No Direct I/O in Will)
        # We use FileHandler to cross the boundary into the 'Body/Infrastructure' layer
        help_file = settings.REPO_PATH / "reports" / "cli_help.txt"
        await FileHandler.ensure_parent_dir(help_file)
        await FileHandler.write_content(help_file, help_text)

        # 4. Cognitive Processing
        cognitive_service = CognitiveService(settings.REPO_PATH)
        translator = IntentTranslator(cognitive_service)

        # IntentTranslator might still be sync, so we offload to thread
        response_text = await asyncio.to_thread(translator.translate, user_input)
        response_json = extract_json_from_response(response_text)

        if not response_json:
            raise json.JSONDecodeError(
                "No valid JSON found in response.", response_text, 0
            )

        # 5. Result Presentation (UI Layer - Typer allowed here in CLI Logic)
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
    except Exception as e:
        logger.exception("An unexpected error occurred in chat logic")
        raise typer.Exit(code=1)
