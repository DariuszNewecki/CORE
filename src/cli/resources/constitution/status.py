# src/body/cli/resources/constitution/status.py
import typer
from rich.console import Console

from cli.logic import governance_logic
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("status")
@core_command(dangerous=False, requires_context=True)
# ID: 7b039cb6-ea90-4bfc-aa1b-1d2eea60a34f
def status_coverage(ctx: typer.Context) -> None:
    """
    Show enforcement coverage status for the entire constitution.

    Identifies 'Enforced' vs 'Declared' rules to detect governance gaps.
    """
    core_context = ctx.obj
    repo_root = core_context.git_service.repo_path

    console.print(
        "[bold cyan]📊 Mapping Constitutional Enforcement Coverage...[/bold cyan]"
    )

    # Extracts data from the mapping engine (JSON Law vs YAML Mappings)
    coverage_data = governance_logic.get_coverage_data(
        repo_root, core_context.file_handler
    )

    summary = coverage_data.get("summary", {})
    console.print(f"\nTotal Rules: {summary.get('rules_total')}")
    console.print(f"Enforced   : [green]{summary.get('rules_enforced')}[/green]")
    console.print(f"Coverage   : [bold]{summary.get('execution_rate')}%[/bold]")
