# src/cli/resources/constitution/status.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from cli.logic import governance_logic
from cli.utils import core_command

from . import app


console = Console()


@app.command("status")
@core_command(dangerous=False, requires_context=True)
# ID: d4c140ee-0765-402c-9a60-7b84909bad43
def status_coverage(ctx: typer.Context) -> None:
    """
    Show enforcement coverage status for the entire constitution.

    Identifies 'Enforced' vs 'Declared' rules to detect governance gaps.
    """
    core_context = ctx.obj
    repo_root = core_context.git_service.repo_path
    logger.info(
        "[bold cyan]📊 Mapping Constitutional Enforcement Coverage...[/bold cyan]"
    )
    coverage_data = governance_logic.get_coverage_data(
        repo_root, core_context.file_handler
    )
    summary = coverage_data.get("summary", {})
    logger.info("\nTotal Rules: %s", summary.get("rules_total"))
    logger.info("Enforced   : [green]%s[/green]", summary.get("rules_enforced"))
    logger.info("Coverage   : [bold]%s%[/bold]", summary.get("execution_rate"))
