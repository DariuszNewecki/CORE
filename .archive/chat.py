# src/api/cli/chat.py
# ID: api.cli.chat
"""
AI-assisted CLI command translation.

CONSTITUTIONAL COMPLIANCE:
- API layer entrypoint that delegates to Will layer for decision-making
- Uses dependency injection (no direct settings access)
- Delegates file I/O to Body layer services
- Routes all AI decisions through Will layer agents

Architecture:
    User Input (API/CLI boundary)
        ↓
    Intent Translation (Will layer)
        ↓
    Constitutional Rules (Mind layer - consulted by Will)
        ↓
    Command Execution (Body layer - delegated by Will)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv

from shared.context import CoreContext
from shared.infrastructure.config_service import config_service
from shared.logger import getLogger
from shared.utils.parsing import extract_json_from_response
from shared.utils.subprocess_utils import run_command_async
from will.agents.intent_translator import IntentTranslator
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
load_dotenv()


# ID: 2f40b3b9-6b2b-4e4d-9a32-3d1a0b2e1d9c
async def _require_llm_enabled() -> None:
    """Fails fast if LLMs are not enabled in runtime configuration."""
    llm_enabled = await config_service.get_bool("LLM_ENABLED", default=False)
    if not llm_enabled:
        logger.error(
            "The 'chat' command requires LLMs to be enabled. Check 'LLM_ENABLED' in the database."
        )
        raise typer.Exit(code=1)


# ID: 8b8a3ef2-4bb3-44d8-9cb8-6ec3b36f2aa0
async def _get_registered_cli_help_text(repo_path: Path) -> str:
    """
    Retrieves CLI help text for a canonical, registry-backed command.

    We intentionally avoid `core-admin --help` because it is not a registered command
    name under the `group.action` convention enforced by `respect_cli_registry_check`.
    """
    args = ["poetry", "run", "core-admin", "check", "audit", "--help"]
    result = await run_command_async(args, cwd=repo_path)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        logger.error(
            "Failed to generate CLI help text for %s: %s", "check.audit", stderr
        )
        raise typer.Exit(code=1)

    return result.stdout or ""


# ID: 1d6e2f1d-0d0a-4e3f-9c25-6b3a9d1c7a6d
async def _persist_cli_help_text(repo_path: Path, help_text: str) -> Path:
    """
    Persists help text via Body layer infrastructure.

    CONSTITUTIONAL FIX: API layer delegates file I/O to Body services.
    This function coordinates the delegation but does not perform I/O directly.
    """
    # CONSTITUTIONAL FIX: Import Body service for file operations
    from body.services.file_service import FileService

    file_service = FileService(repo_path)
    help_file = await file_service.write_report("cli_help.txt", help_text)
    return help_file


# ID: e28b1579-1e68-40e2-9583-6774d0e8e48f
async def chat(
    ctx: typer.Context,
    user_input: str = typer.Argument(..., help="Your goal in natural language."),
) -> None:
    """
    Assesses a natural language goal and returns a clear, actionable CLI command suggestion.

    CONSTITUTIONAL COMPLIANCE:
    - API entrypoint that delegates to Will layer
    - Uses injected CoreContext (no direct settings access)
    - Delegates file operations to Body layer
    """
    await _require_llm_enabled()

    # CONSTITUTIONAL FIX: Get context from CLI framework injection
    core_context: CoreContext = ctx.obj
    repo_path = core_context.repo_path

    logger.info("Translating user goal: %r", user_input)

    response_text: str | None = None
    try:
        # 1) Generate context via safe subprocess wrapper (registered command only)
        help_text = await _get_registered_cli_help_text(repo_path)

        # 2) CONSTITUTIONAL FIX: Delegate file I/O to Body layer
        help_file = await _persist_cli_help_text(repo_path, help_text)
        logger.debug("Wrote CLI help context to: %s", help_file)

        # 3) WILL LAYER: Cognitive processing / translation
        # Will layer makes the decision about command translation
        cognitive_service = CognitiveService(repo_path)
        translator = IntentTranslator(cognitive_service)

        # IntentTranslator may be sync; offload to a worker thread.
        response_text = await asyncio.to_thread(translator.translate, user_input)
        response_json: dict[str, Any] | None = extract_json_from_response(response_text)

        if not response_json:
            raise json.JSONDecodeError(
                "No valid JSON found in response.", response_text, 0
            )

        # 4) Presentation (API layer responsibility)
        command = response_json.get("command")
        error_message = response_json.get("error")

        if command:
            typer.secho("\nAI Suggestion:", fg=typer.colors.GREEN)
            typer.echo("Recommended command to achieve your goal:")
            typer.secho(f"\n  {command}\n", fg=typer.colors.CYAN)
            return

        if error_message:
            typer.secho("\nAI Assessment:", fg=typer.colors.YELLOW)
            typer.echo(str(error_message))
            return

        raise KeyError("AI response missing 'command' or 'error' key.")

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse the AI translation: %s", e)
        typer.echo("The AI returned a response that could not be interpreted.")
        if response_text:
            typer.echo("Raw response:")
            typer.echo(response_text)
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception:
        logger.exception("Unexpected error occurred in chat logic")
        raise typer.Exit(code=1)
