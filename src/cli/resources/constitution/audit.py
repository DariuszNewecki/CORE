# src/cli/resources/constitution/audit.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from mind.governance.filtered_audit import run_filtered_audit
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("audit")
@core_command(dangerous=False, requires_context=True)
# ID: d12aedfe-884a-4223-9f4c-9cb2c10dfa41
async def audit_policies(
    ctx: typer.Context,
    policy: list[str] = typer.Option(
        [], "--policy", "-p", help="Policy IDs to execute."
    ),
    rule: list[str] = typer.Option(
        [], "--rule", "-r", help="Specific rule IDs to execute."
    ),
) -> None:
    """
    Execute targeted constitutional audits for specific policies or rules.

    Example: core-admin constitution audit --policy standard_code_linkage
    """
    if not policy and (not rule):
        logger.info(
            "[red]Error: Must specify at least one --policy or --rule filter.[/red]"
        )
        raise typer.Exit(1)
    auditor_context = ctx.obj.auditor_context
    logger.info(
        "[bold cyan]🔍 Executing targeted audit for %s items...[/bold cyan]",
        len(policy or rule),
    )
    findings, _executed_ids, stats = await run_filtered_audit(
        auditor_context, policy_ids=policy or None, rule_ids=rule or None
    )
    logger.info(
        "\n[bold]Audit Complete:[/bold] %s rules checked.", stats["executed_rules"]
    )
    if not findings:
        logger.info("[green]✅ No violations found.[/green]")
    else:
        logger.info("[red]❌ Found %s violations.[/red]", len(findings))
