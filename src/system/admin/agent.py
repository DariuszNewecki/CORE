# src/system/admin/agent.py
"""
Intent: Exposes PlannerAgent capabilities directly to the human operator via the CLI.
"""
from pathlib import Path
import typer
from core.clients import GeneratorClient, OrchestratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from shared.logger import getLogger
from shared.path_utils import get_repo_root
from agents.planner_agent import PlannerAgent

log = getLogger("core_admin.agent")
CORE_ROOT = get_repo_root()

agent_app = typer.Typer(help="Directly invoke autonomous agent capabilities.")


@agent_app.command("scaffold")
def agent_scaffold(
    name: str = typer.Argument(
        ...,
        help="The directory name for the new application (e.g., 'my-web-app').",
    ),
    goal: str = typer.Argument(
        ...,
        help="A high-level goal for the new application (e.g., 'a simple web calculator').",
    ),
    git_init: bool = typer.Option(
        True,
        "--git/--no-git",
        help="Initialize a new Git repository in the created application's directory.",
    ),
):
    """
    Uses the PlannerAgent to autonomously scaffold a new application.
    """
    log.info(f"🤖 Invoking PlannerAgent to scaffold application '{name}'...")
    log.info(f"   -> Goal: '{goal}'")

    try:
        # The agent and its tools are always initialized relative to the CORE repo root.
        planner = PlannerAgent(
            orchestrator_client=OrchestratorClient(),
            generator_client=GeneratorClient(),
            file_handler=FileHandler(str(CORE_ROOT)),
            git_service=GitService(str(CORE_ROOT)),
            intent_guard=IntentGuard(CORE_ROOT),
        )

        success, message = planner.scaffold_new_application(
            project_name=name, goal=goal, initialize_git=git_init
        )

    except Exception as e:
        log.error(f"❌ Failed to initialize agent and its tools: {e}", exc_info=True)
        raise typer.Exit(code=1)

    if success:
        typer.secho(f"\n{message}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\n{message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def register(app: typer.Typer):
    """Register the 'agent' command group with the main CLI app."""
    app.add_typer(agent_app, name="agent")