# src/body/cli/resources/code/lint.py
import typer
from rich.console import Console

from mind.enforcement.audit import lint
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("lint")
@core_command(dangerous=False, requires_context=True)
# ID: 9db9ad62-1a9e-46b4-bfd2-7b7ea8856930
async def lint_command(ctx: typer.Context) -> None:
    """Check code quality using Black and Ruff (Read-Only)."""
    console.print("[bold cyan]🔎 Linting codebase...[/bold cyan]")

    # Reuses the logic from the Mind enforcement layer
    lint()
