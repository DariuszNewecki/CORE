# src/cli/resources/dev/strategic_audit.py
"""
Strategic Audit command — CORE's self-awareness cycle.

Wires 'core-admin dev strategic-audit' to the StrategicAuditor agent.
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from cli.utils import core_command
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
# ID: 0261fa1c-e876-4f07-83c2-dab6742ae7e6
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
    if execute:
        write = True
    async with get_session() as session:
        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            logger.info(
                "[red]❌ LLM_ENABLED is False. Enable LLMs in database settings to use strategic audit.[/red]"
            )
            raise typer.Exit(code=1)
    mode_parts = []
    if write:
        mode_parts.append("WRITE")
    if execute:
        mode_parts.append("EXECUTE")
    mode = " + ".join(mode_parts) if mode_parts else "DRY-RUN"
    logger.info(
        "\n[bold cyan]🧠 CORE Strategic Audit[/bold cyan] [dim](%s)[/dim]\n", mode
    )
    try:
        cognitive_service = await context.registry.get_cognitive_service()
        auditor = StrategicAuditor(context=context, cognitive_service=cognitive_service)
        async with get_session() as session:
            campaign = await auditor.run(
                session=session, write=write, execute_autonomous=execute
            )
        if campaign.escalations:
            logger.info(
                "\n[bold yellow]📬 %s escalation(s) require your review.[/bold yellow]",
                campaign.escalation_count,
            )
            logger.info(
                "[dim]These need .intent/ amendments — only you can approve them.[/dim]\n"
            )
            for i, e in enumerate(campaign.escalations, 1):
                logger.info("  [yellow]%s.[/yellow] %s", i, e.root_cause)
                logger.info("     [dim]%s[/dim]", e.proposed_fix[:120])
        if write:
            logger.info(
                "\n[green]✅ Campaign persisted.[/green] [dim]ID: %s[/dim]",
                campaign.campaign_id,
            )
        else:
            logger.info(
                "\n[dim]Dry-run complete. Use --write to persist, --execute to act.[/dim]"
            )
    except Exception as e:
        logger.exception("Strategic audit failed")
        logger.info("[red]❌ Strategic audit failed: %s[/red]", e)
        raise typer.Exit(code=1)
