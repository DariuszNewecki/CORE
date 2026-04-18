# src/cli/resources/code/test.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.utils import core_command
from mind.enforcement.audit import test_system

from .hub import app


console = Console()


@app.command("test")
@core_command(dangerous=False, requires_context=True)
# ID: b89ff2a7-0bf3-47cf-90ba-66a3801630c3
async def test_command(ctx: typer.Context) -> None:
    """Run the project test suite via pytest."""
    logger.info("[bold cyan]🧪 Running test suite...[/bold cyan]")
    return await test_system()
