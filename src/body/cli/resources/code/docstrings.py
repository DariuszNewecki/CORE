# src/body/cli/resources/code/docstrings.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("docstrings")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: df2829b7-82c5-4350-80bb-8931530eec92
async def fix_docstrings_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply AI-generated docstrings to files."
    ),
) -> None:
    """
    Autonomously generate and inject missing docstrings using AI.

    Scans the codebase for public functions lacking documentation and
    proposes/applies fixes based on implementation analysis.
    """
    core_context: CoreContext = ctx.obj

    mode = "WRITE" if write else "DRY-RUN"
    console.print(f"[bold cyan]✍️  Repairing Docstrings ({mode})...[/bold cyan]")

    # Routes to the fix.docstrings atomic action
    await core_context.action_executor.execute("fix.docstrings", write=write)
