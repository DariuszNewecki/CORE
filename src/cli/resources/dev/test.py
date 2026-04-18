# src/cli/resources/dev/test.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.logic.interactive_test_logic import run_interactive_test_generation
from cli.utils import core_command

from .hub import app


console = Console()


@app.command("test")
@core_command(dangerous=True, requires_context=True)
# ID: ffdee379-1a1e-429f-9dab-3ceaaa85ae1f
async def test_interactive(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Path to the file you want to test."),
) -> None:
    """
    Start an interactive test generation session for a specific file.

    Allows you to review, edit, and approve test code step-by-step.
    """
    core_context = ctx.obj
    logger.info(
        "[bold cyan]🎯 Starting interactive test session for:[/bold cyan] %s", target
    )
    success = await run_interactive_test_generation(
        target_file=target, core_context=core_context
    )
    if not success:
        raise typer.Exit(1)
