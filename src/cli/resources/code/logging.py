# src/cli/resources/code/logging.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


console = Console()


@app.command("logging")
@command_meta(
    canonical_name="code.logging",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Standardize logging across the codebase.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: 5076493c-79a8-4f92-8c15-ddfd695d4275
async def fix_logging_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Convert print() to logger calls."
    ),
) -> None:
    """
    Standardize logging across the codebase.

    Replaces print() statements and malformed f-strings in loggers with
    constitutional standard logging (LOG-001/LOG-003).
    """
    core_context: CoreContext = ctx.obj
    mode = "Applying" if write else "Analyzing"
    logger.info("[bold cyan]🪵  %s Logging Standards...[/bold cyan]", mode)
    await core_context.action_executor.execute("fix.logging", write=write)
