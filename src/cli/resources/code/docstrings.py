# src/cli/resources/code/docstrings.py
import typer

from body.self_healing.docstring_service import fix_docstrings
from cli.utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


@app.command("docstrings")
@command_meta(
    canonical_name="code.docstrings",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Heal missing docstrings using constitutional reasoning.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: 9f0d0239-d29d-4dff-8c32-3fdecaa809e9
async def fix_docstrings_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes."),
    limit: int = typer.Option(3, "--limit", help="Symbols to process."),
    verbose: bool = typer.Option(False, "--verbose", help="Show detail."),
) -> None:
    """Autonomously generate and inject missing docstrings using AI."""
    await fix_docstrings(context=ctx.obj, write=write, limit=limit)
