# src/system/admin/develop.py
"""
Intent: Implements the `core-admin develop` command, which is the primary
entry point for CORE's autonomous self-development loop. This command
orchestrates the full "goal -> plan -> execute" cycle.
"""
import asyncio

import typer
from dotenv import load_dotenv

from agents.development_cycle import run_development_cycle
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.develop")


# This is the capability tag that will link this command to the constitution.
# CAPABILITY: autonomous_development
def develop(
    goal: str = typer.Argument(
        ...,  # '...' makes the argument required
        help="The high-level development goal for CORE to achieve.",
    ),
):
    """
    Orchestrates the autonomous development process from a high-level goal.
    """
    log.info(f"🚀 Received new development goal: '{goal}'")

    # This command requires the LLMs to be enabled.
    load_dotenv()
    if not settings.LLM_ENABLED:
        log.error("❌ The 'develop' command requires LLMs to be enabled.")
        log.error("   Please set the required API keys in your .env file.")
        raise typer.Exit(code=1)

    # Run the asynchronous development cycle from our synchronous CLI command.
    success, message = asyncio.run(run_development_cycle(goal))

    # Report the final outcome to the user.
    if success:
        typer.secho("\n✅ Goal achieved successfully.", fg=typer.colors.GREEN)
        typer.secho(f"   -> {message}", fg=typer.colors.GREEN)
    else:
        typer.secho("\n❌ Goal execution failed.", fg=typer.colors.RED)
        typer.secho(f"   -> {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def register(app: typer.Typer):
    """Register the 'develop' command with the main CLI app."""
    app.command("develop")(develop)
