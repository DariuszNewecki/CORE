# src/body/cli/admin_cli.py
# ID: body.cli.admin_cli

"""
The single, canonical entry point for the core-admin CLI.

Constitutional Alignment:
- Implements the 'Golden Tree' hierarchy (V2.5).
- Restores all legacy top-level commands to prevent workflow breakage.
- No direct settings access (delegates to infrastructure bootstrap).
"""

from __future__ import annotations

import typer
from rich.console import Console

# Import all original command modules for fidelity restoration
from body.cli.commands import (
    check_atomic_actions,
    coverage,
    enrich,
    governance,
    inspect,
    interactive_test,
    run,
    search,
    secrets,
    submit,
)
from body.cli.commands.autonomy import autonomy_app
from body.cli.commands.check import check_app
from body.cli.commands.components import components_app
from body.cli.commands.dev_sync import dev_sync_app
from body.cli.commands.develop import develop_app
from body.cli.commands.diagnostics import app as diagnostics_app
from body.cli.commands.fix import fix_app
from body.cli.commands.manage import manage
from body.cli.commands.refactor import refactor_app
from body.cli.commands.status import status_app
from body.cli.interactive import launch_interactive_menu
from body.cli.logic.tools import tools_app

# Infrastructure & Registry
from body.infrastructure.bootstrap import create_core_context
from body.services.service_registry import service_registry
from shared.infrastructure.context import cli as context_cli
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


console = Console()
logger = getLogger(__name__)

app = typer.Typer(
    name="core-admin",
    help=(
        "\n    CORE: The Self-Improving System Architect's Toolkit.\n"
        "    This CLI is the primary interface for operating and governing the CORE system.\n"
    ),
    no_args_is_help=False,
)

# Bootstrap context (Reads settings in sanctuary)
core_context = create_core_context(service_registry)


# ID: c1414598-a5f8-46c2-8ff9-3a141bea3b11
def register_all_commands(app_instance: typer.Typer) -> None:
    """Registers the 7 Golden Domains + all 24 legacy commands for compatibility."""

    # --- GOLDEN TIER 1 (The Organized Hierarchy) ---
    app_instance.add_typer(status_app, name="status")  # Domain 1: Sensation
    app_instance.add_typer(check_app, name="check")  # Domain 2: Verification
    app_instance.add_typer(fix_app, name="fix")  # Domain 3: Remediation
    app_instance.add_typer(develop_app, name="develop")  # Domain 4: Autonomy
    app_instance.add_typer(
        inspect.inspect_app, name="inspect"
    )  # Domain 5: Introspection
    app_instance.add_typer(manage.manage_app, name="manage")  # Domain 6: Administration
    app_instance.add_typer(submit.submit_app, name="submit")  # Domain 7: Integration

    # --- LEGACY COMPATIBILITY (Restoring all original commands) ---
    app_instance.add_typer(dev_sync_app, name="dev")
    app_instance.add_typer(autonomy_app, name="autonomy")
    app_instance.add_typer(coverage.coverage_app, name="coverage")
    app_instance.add_typer(diagnostics_app, name="diagnostics")
    app_instance.add_typer(context_cli.app, name="context")
    app_instance.add_typer(search.search_app, name="search")
    app_instance.add_typer(secrets.app, name="secrets")
    app_instance.add_typer(
        check_atomic_actions.atomic_actions_group, name="atomic-actions"
    )
    #    app_instance.add_typer(mind_app, name="mind")
    app_instance.add_typer(components_app, name="components")
    app_instance.add_typer(interactive_test.app, name="interactive-test")
    app_instance.add_typer(tools_app, name="tools")
    app_instance.add_typer(refactor_app, name="refactor")
    app_instance.add_typer(run.run_app, name="run")
    app_instance.add_typer(enrich.enrich_app, name="enrich")
    app_instance.add_typer(governance.governance_app, name="governance")


# Apply full registration
register_all_commands(app)


@app.callback(invoke_without_command=True)
# ID: 2429907d-f6f1-47a5-a3af-5df18685c545
def main(ctx: typer.Context) -> None:
    """Main entry point for core-admin CLI."""
    service_registry.prime(get_session)
    ctx.obj = core_context

    if ctx.invoked_subcommand is None:
        console.print(
            "[bold green]🏛️  CORE Admin Active. Use [cyan]--help[/cyan] to see all commands.[/bold green]"
        )
        launch_interactive_menu()


if __name__ == "__main__":
    app()
