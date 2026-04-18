# src/cli/resources/project/docs.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.logic.project_docs import docs as generate_docs
from cli.utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from . import app


console = Console()


@app.command("docs")
@command_meta(
    canonical_name="project.docs",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Generate capability documentation.",
)
@core_command(dangerous=False, requires_context=False)
# ID: 6759f022-9e30-474c-8ea3-4740ee55249c
def generate_project_docs(
    output: str = typer.Option(
        "docs/10_CAPABILITY_REFERENCE.md",
        "--output",
        "-o",
        help="Target path for the reference doc.",
    ),
) -> None:
    """
    Generate the canonical Capability Reference documentation.

    Extracts all public symbols and their intent from the database.
    """
    logger.info(
        "[bold cyan]📚 Generating capability reference to:[/bold cyan] %s", output
    )
    generate_docs(output=output)
    logger.info("[green]✅ Documentation updated.[/green]")
