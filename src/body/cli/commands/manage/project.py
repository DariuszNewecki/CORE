# src/body/cli/commands/manage/project.py

"""Refactored logic for src/body/cli/commands/manage/project.py."""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.logic.byor import initialize_repository
from body.cli.logic.project_docs import docs as project_docs
from features.project_lifecycle.scaffolding_service import create_new_project
from shared.cli_utils import core_command


console = Console()
project_sub_app = typer.Typer(help="Manage CORE projects.", no_args_is_help=True)


@project_sub_app.command("new")
@core_command(dangerous=True, confirmation=True)
# ID: 91218c07-8c1b-4ec5-8955-249522d49f10
def project_new_command(
    ctx: typer.Context,
    name: str = typer.Argument(...),
    profile: str = "default",
    write: bool = False,
):
    """Scaffold a new CORE-governed application."""
    dry_run = not write
    console.print(
        f"[bold cyan]🚀 Creating project[/bold cyan]: '{name}' (dry_run={dry_run})"
    )
    try:
        create_new_project(name=name, profile=profile, dry_run=dry_run)
        if not dry_run:
            console.print(
                f"[bold green]✅ Project '{name}' scaffolded successfully.[/bold green]"
            )
    except Exception as e:
        console.print(f"[bold red]❌ {e}[/bold red]")
        raise typer.Exit(1)


project_sub_app.command("onboard")(initialize_repository)
project_sub_app.command("docs")(project_docs)
