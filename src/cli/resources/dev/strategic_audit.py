# src/cli/resources/dev/strategic_audit.py
# ID: cli.resources.dev.strategic_audit

"""
Strategic Audit command — CORE's self-awareness cycle.

Wires 'core-admin dev strategic-audit' to the StrategicAuditor agent.
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
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
# ID: dev-strategic-audit-cmd-001
# ID: beba01c8-fafa-4692-a474-9cd30e02a195
async def strategic_audit_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Persist campaign to database."),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Immediately execute autonomous tasks (implies --write).",
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

    # --execute implies --write
    if execute:
        write = True

    # Pre-flight: LLM must be enabled
    async with get_session() as session:
        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            console.print(
                "[red]❌ LLM_ENABLED is False. "
                "Enable LLMs in database settings to use strategic audit.[/red]"
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

        auditor = StrategicAuditor(
            context=context,
            cognitive_service=cognitive_service,
        )

        async with get_session() as session:
            campaign = await auditor.run(
                session=session,
                write=write,
                execute_autonomous=execute,
            )

        # Human summary already printed by auditor._log_summary()
        # Print escalations prominently if any
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
                f"\n[green]✅ Campaign persisted.[/green] "
                f"[dim]ID: {campaign.campaign_id}[/dim]"
            )
        else:
            console.print(
                "\n[dim]Dry-run complete. Use --write to persist, --execute to act.[/dim]"
            )

    except Exception as e:
        logger.exception("Strategic audit failed")
        console.print(f"[red]❌ Strategic audit failed: {e}[/red]")
        raise typer.Exit(code=1)
