# src/body/cli/resources/code/test.py
import typer
from rich.console import Console

from mind.enforcement.audit import test_system
from shared.cli_utils import core_command

from .hub import app


console = Console()


@app.command("test")
@core_command(dangerous=False, requires_context=True)
# ID: b6829b77-60e6-455b-a258-050eeb348dc9
async def test_command(ctx: typer.Context) -> None:
    """Run the project test suite via pytest."""
    console.print("[bold cyan]🧪 Running test suite...[/bold cyan]")

    # test_system is an @atomic_action that returns an ActionResult
    # result display is handled by the @core_command decorator
    return await test_system()
