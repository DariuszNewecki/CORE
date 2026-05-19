# src/cli/resources/code/lint.py
import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


console = Console()


@app.command("lint")
@core_command(dangerous=False, requires_context=False)
# ID: 044f8edf-3262-4e8b-b394-fd76bdd74136
async def lint_command() -> None:
    """Check code quality using Black and Ruff (Read-Only)."""
    console.print("[bold cyan]🔎 Linting codebase...[/bold cyan]")
    client = CoreApiClient()
    result = await client.lint()

    if result.get("error"):
        console.print(f"[red]Lint failed: {result['error']}[/red]")
        raise typer.Exit(1)

    for tool_name, tool_result in result.get("tools", {}).items():
        rc = tool_result["returncode"]
        marker = "[green]✓[/green]" if rc == 0 else "[red]✗[/red]"
        console.print(f"{marker} {tool_name} (returncode={rc})")
        if tool_result.get("stdout"):
            console.print(tool_result["stdout"], highlight=False, end="")
        if tool_result.get("stderr"):
            console.print(tool_result["stderr"], highlight=False, end="")

    if not result.get("ok"):
        raise typer.Exit(1)
