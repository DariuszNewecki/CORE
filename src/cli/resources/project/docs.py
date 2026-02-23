# src/body/cli/resources/project/docs.py
import typer
from rich.console import Console

from cli.logic.project_docs import docs as generate_docs
from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from . import app


console = Console()


@app.command("docs")
@command_meta(
    canonical_name="project.docs",
    behavior=CommandBehavior.READ,  # Tell CORE this is just a read operation
    layer=CommandLayer.BODY,
    summary="Generate capability documentation.",
)
@core_command(dangerous=False, requires_context=False)
# ID: b031ae16-fe8d-4ffa-8bd4-6eddf74f7cf0
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
    console.print(
        f"[bold cyan]📚 Generating capability reference to:[/bold cyan] {output}"
    )

    # Delegates to the logic layer which uses runpy
    generate_docs(output=output)

    console.print("[green]✅ Documentation updated.[/green]")
