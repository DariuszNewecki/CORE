# src/body/cli/resources/dev/test.py
import typer
from rich.console import Console

from cli.logic.interactive_test_logic import run_interactive_test_generation
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("test")
@core_command(dangerous=True, requires_context=True)
# ID: 86e90ce7-e818-4609-baa9-f9867e1aec36
async def test_interactive(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Path to the file you want to test."),
) -> None:
    """
    Start an interactive test generation session for a specific file.

    Allows you to review, edit, and approve test code step-by-step.
    """
    core_context = ctx.obj
    console.print(
        f"[bold cyan]🎯 Starting interactive test session for:[/bold cyan] {target}"
    )

    # Delegates to the interactive logic package (Octopus Reflex loop)
    success = await run_interactive_test_generation(
        target_file=target, core_context=core_context
    )

    if not success:
        raise typer.Exit(1)
