# src/cli/resources/code/format.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.self_healing.code_style_service import format_code
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("format")
@core_command(dangerous=True, requires_context=True)
# ID: 3dfcec28-34fd-44d4-9aec-bcbf29eb6d76
async def format_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply formatting changes to disk."
    ),
) -> None:
    """
    Format code using Black and Ruff.

    Defaults to dry-run mode. Use --write to apply changes.
    """
    mode = "Applying" if write else "Checking"
    logger.info("[bold cyan]✨ %s code formatting (Black + Ruff)...[/bold cyan]", mode)
    format_code(write=write)
    if not write:
        logger.info("\n[yellow]💡 Run with --write to apply these changes.[/yellow]")


@app.command("format-imports")
@core_command(dangerous=True, requires_context=True)
# ID: 582d69b9-6f50-411a-a950-37e66ce2e07b
async def format_imports_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply import sorting to disk."),
) -> None:
    """
    Sort and group Python imports according to PEP 8 / Constitutional standards.
    Uses Ruff's import sorter (I) rules.
    """
    core_context = ctx.obj
    await core_context.action_executor.execute("fix.imports", write=write)
