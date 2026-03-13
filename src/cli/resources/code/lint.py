# src/cli/resources/code/lint.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from mind.enforcement.audit import lint
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("lint")
@core_command(dangerous=False, requires_context=True)
# ID: 044f8edf-3262-4e8b-b394-fd76bdd74136
async def lint_command(ctx: typer.Context) -> None:
    """Check code quality using Black and Ruff (Read-Only)."""
    logger.info("[bold cyan]🔎 Linting codebase...[/bold cyan]")
    lint()
