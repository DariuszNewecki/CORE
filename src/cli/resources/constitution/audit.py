# src/body/cli/resources/constitution/audit.py
import typer
from rich.console import Console

from mind.governance.filtered_audit import run_filtered_audit
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("audit")
@core_command(dangerous=False, requires_context=True)
# ID: 5cfb9f48-edc3-4169-9c9f-17f5c79896d1
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
    if not policy and not rule:
        console.print(
            "[red]Error: Must specify at least one --policy or --rule filter.[/red]"
        )
        raise typer.Exit(1)

    auditor_context = ctx.obj.auditor_context
    console.print(
        f"[bold cyan]🔍 Executing targeted audit for {len(policy or rule)} items...[/bold cyan]"
    )

    # Reuses the robust filtered audit engine
    findings, _executed_ids, stats = await run_filtered_audit(
        auditor_context, policy_ids=policy or None, rule_ids=rule or None
    )

    console.print(
        f"\n[bold]Audit Complete:[/bold] {stats['executed_rules']} rules checked."
    )
    if not findings:
        console.print("[green]✅ No violations found.[/green]")
    else:
        console.print(f"[red]❌ Found {len(findings)} violations.[/red]")
