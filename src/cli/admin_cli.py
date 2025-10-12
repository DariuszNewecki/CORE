# src/cli/admin_cli.py
"""
The single, canonical entry point for the core-admin CLI.
This module assembles all command groups into a single Typer application.
"""

from __future__ import annotations

import typer

# --- START MODIFICATION: Import modules directly ---
from cli.commands import check, fix, inspect, manage, mind, run, search, submit
from cli.interactive import launch_interactive_menu
from cli.logic import audit as audit_logic

# --- END MODIFICATION ---
from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.git_service import GitService
from features.governance.audit_context import AuditorContext
from rich.console import Console
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlannerConfig

console = Console()
log = getLogger("admin_cli")

app = typer.Typer(
    name="core-admin",
    help="""
    CORE: The Self-Improving System Architect's Toolkit.
    This CLI is the primary interface for operating and governing the CORE system.
    """,
    no_args_is_help=False,
)

core_context = CoreContext(
    git_service=GitService(settings.REPO_PATH),
    cognitive_service=CognitiveService(settings.REPO_PATH),
    qdrant_service=QdrantService(),
    auditor_context=AuditorContext(settings.REPO_PATH),
    file_handler=FileHandler(str(settings.REPO_PATH)),
    planner_config=PlannerConfig(),
)


# ID: 2cefad7a-83b8-4263-b882-5a62eae5b092
def register_all_commands(app_instance: typer.Typer) -> None:
    """Register all command groups and inject context declaratively."""
    # 1. Add top-level command groups (verbs)
    app_instance.add_typer(check.check_app, name="check")
    app_instance.add_typer(fix.fix_app, name="fix")
    app_instance.add_typer(inspect.inspect_app, name="inspect")
    app_instance.add_typer(manage.manage_app, name="manage")
    app_instance.add_typer(mind.mind_app, name="mind")
    app_instance.add_typer(run.run_app, name="run")
    app_instance.add_typer(search.search_app, name="search")
    app_instance.add_typer(submit.submit_app, name="submit")

    # 2. Inject context where needed
    modules_with_context = [check, fix, inspect, manage, run, search, submit]
    for module in modules_with_context:
        if hasattr(module, "set_context"):
            module.set_context(core_context)

    if hasattr(audit_logic, "set_context"):
        audit_logic.set_context(core_context)


register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 74b366e2-d1fc-44c6-a9bc-e8fe222d1ad8
def main(ctx: typer.Context):
    """If no command is specified, launch the interactive menu."""
    ctx.obj = core_context
    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]No command specified. Launching interactive menu...[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
