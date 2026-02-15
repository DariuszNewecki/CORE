# src/body/cli/resources/code/format.py
import typer
from rich.console import Console

from features.self_healing.code_style_service import format_code
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("format")
@core_command(dangerous=True, requires_context=True)
# ID: 2d58b4be-eeee-433a-b111-5d1198bfa0d7
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
    console.print(f"[bold cyan]✨ {mode} code formatting (Black + Ruff)...[/bold cyan]")

    # Delegates to the established style service
    format_code(write=write)

    if not write:
        console.print("\n[yellow]💡 Run with --write to apply these changes.[/yellow]")


@app.command("format-imports")
@core_command(dangerous=True, requires_context=True)
# ID: b892c98f-cc17-4bda-87b5-1323cdfc7b95
async def format_imports_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply import sorting to disk."),
) -> None:
    """
    Sort and group Python imports according to PEP 8 / Constitutional standards.
    Uses Ruff's import sorter (I) rules.
    """
    core_context = ctx.obj
    # Routes to the fix.imports atomic action
    await core_context.action_executor.execute("fix.imports", write=write)
