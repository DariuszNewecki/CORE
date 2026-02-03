# src/body/cli/resources/code/audit.py
from pathlib import Path

import typer
from rich.console import Console

from mind.governance.auditor import ConstitutionalAuditor
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("audit")
@core_command(dangerous=False, requires_context=True)
# ID: e4570c9b-6eab-4ee5-86d2-7a772532dbc3
async def audit_command(
    ctx: typer.Context,
    target: Path = typer.Argument(Path("src"), help="Directory or file to audit."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show individual findings."
    ),
) -> None:
    """Run the full constitutional self-audit on the codebase."""
    console.print(
        f"[bold cyan]⚖️  Running constitutional audit on {target}...[/bold cyan]"
    )

    # Uses the wired context from the framework
    auditor_context = ctx.obj.auditor_context
    auditor = ConstitutionalAuditor(auditor_context)

    # ConstitutionalAuditor.run_full_audit_async handles findings and reporting
    await auditor.run_full_audit_async()
