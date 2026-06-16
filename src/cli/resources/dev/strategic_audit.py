# src/cli/resources/dev/strategic_audit.py
"""
Strategic Audit command — CORE's self-awareness cycle.

Wires 'core-admin dev strategic-audit' to the StrategicAuditor agent.
"""

from __future__ import annotations

import logging

import typer
from dotenv import load_dotenv
from rich.console import Console

from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("strategic-audit")
@command_meta(
    canonical_name="dev.strategic_audit",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Run CORE's self-awareness cycle: audit → reason → campaign → (optionally) execute.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: 0261fa1c-e876-4f07-83c2-dab6742ae7e6
async def strategic_audit_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Persist campaign to database."),
    execute: bool = typer.Option(
        False,
        "--execute",
        help=(
            "Run this campaign's already-approved clusters (implies --write). A new "
            "campaign has none yet — review and accept per cluster first via "
            "'dev campaign'."
        ),
    ),
) -> None:
    """
    Run CORE's strategic self-awareness cycle.

    Reads the full system state (audit findings, knowledge graph, constitution,
    git history), reasons about it as a whole, and produces a prioritised
    remediation campaign.

    Autonomous tasks are staged in PostgreSQL.
    Tasks requiring .intent/ changes are flagged as escalations for your review.

    Examples:
      core-admin dev strategic-audit                    # dry-run: report only
      core-admin dev strategic-audit --write            # persist campaign to DB
      core-admin dev strategic-audit --write --execute  # persist + execute autonomously
    """
    from will.agents.strategic_auditor import StrategicAuditor

    context: CoreContext = ctx.obj
    load_dotenv()
    if execute:
        write = True
    async with get_session() as session:
        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            console.print(
                "[red]❌ LLM_ENABLED is False. Enable LLMs in database settings to use strategic audit.[/red]"
            )
            raise typer.Exit(code=1)
    mode_parts = []
    if write:
        mode_parts.append("WRITE")
    if execute:
        mode_parts.append("EXECUTE")
    mode = " + ".join(mode_parts) if mode_parts else "DRY-RUN"
    console.print(
        f"\n[bold cyan]🧠 CORE Strategic Audit[/bold cyan] [dim]({mode})[/dim]\n"
    )
    try:
        cognitive_service = await context.registry.get_cognitive_service()
        auditor = StrategicAuditor(context=context, cognitive_service=cognitive_service)
        async with get_session() as session:
            campaign = await auditor.run(
                session=session, write=write, execute_autonomous=execute
            )
        if campaign.escalations:
            console.print(
                f"\n[bold yellow]📬 {campaign.escalation_count} escalation(s) require your review.[/bold yellow]"
            )
            console.print(
                "[dim]These need .intent/ amendments — only you can approve them.[/dim]\n"
            )
            for i, e in enumerate(campaign.escalations, 1):
                console.print(f"  [yellow]{i}.[/yellow] {e.root_cause}")
                console.print(f"     [dim]{e.proposed_fix[:120]}[/dim]")
        if write:
            console.print(
                f"\n[green]✅ Campaign persisted.[/green] [dim]ID: {campaign.campaign_id}[/dim]"
            )
            if campaign.autonomous_task_count:
                console.print(
                    f"\n[bold]{campaign.autonomous_task_count} autonomous cluster(s) "
                    "await your per-cluster review.[/bold]"
                )
                console.print(
                    f"  [dim]Review:[/dim]  core-admin dev campaign list {campaign.parent_task_id}"
                )
                console.print(
                    "  [dim]Accept:[/dim]  core-admin dev campaign accept <cluster task id>"
                )
                console.print(
                    f"  [dim]Execute:[/dim] core-admin dev campaign execute {campaign.parent_task_id}"
                )
            if execute:
                console.print(
                    "\n[dim]--execute ran only already-approved clusters; a new campaign "
                    "has none until you accept them above.[/dim]"
                )
        else:
            console.print(
                "\n[dim]Dry-run complete. Use --write to persist for per-cluster review.[/dim]"
            )
    except Exception as e:
        logger.exception("Strategic audit failed")
        console.print(f"[red]❌ Strategic audit failed: {e}[/red]")
        raise typer.Exit(code=1)
