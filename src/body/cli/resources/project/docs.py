# src/body/cli/resources/project/docs.py
import typer
from rich.console import Console

from body.cli.logic.project_docs import docs as generate_docs
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("docs")
@core_command(dangerous=False, requires_context=False)
# ID: d3fe3510-c14a-438a-ab83-ec7c67044c66
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
