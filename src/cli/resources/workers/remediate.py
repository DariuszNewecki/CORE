# src/cli/resources/workers/remediate.py
"""
Remediation pipeline command.

Chains AuditViolationSensor → ViolationRemediator for a given audit rule.

Usage:
    # Dry-run (default) — sense violations, run LLM + Canary, post proposed
    # fixes to blackboard for review. Nothing written to src/.
    core-admin workers remediate purity.no_ast_duplication

    # Write mode — apply fixes, commit
    core-admin workers remediate purity.no_ast_duplication --write

    # Sense only — just post findings to blackboard, no LLM
    core-admin workers remediate purity.no_ast_duplication --sense-only
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils.decorators import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .run import workers_app


logger = getLogger(__name__)
console = Console()


@workers_app.command("remediate")
@core_command(dangerous=True)
# ID: 75e79945-f796-49d5-ba87-783cae6233d0
async def remediate_cmd(
    ctx: typer.Context,
    rule: str = typer.Argument(
        ..., help="Audit rule ID to remediate (e.g. 'purity.no_ast_duplication')."
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply fixes to src/ and commit. Default is dry-run: LLM + Canary run but nothing is written.",
    ),
    sense_only: bool = typer.Option(
        False,
        "--sense-only",
        help="Only run the sensor — post findings to blackboard, skip LLM.",
    ),
) -> None:
    """
    Run the autonomous remediation pipeline for a constitutional audit rule.

    Default (dry-run): sensor finds violations → LLM proposes fix →
    Canary validates → proposed fix posted to blackboard for review.

    With --write: same pipeline but fix is applied to src/ and committed.

    With --sense-only: only the sensor runs — violations are posted to
    the blackboard but no LLM is invoked.

    Examples:
        # Dry-run — review proposed fixes on the blackboard first
        core-admin workers remediate purity.no_ast_duplication

        # Apply fixes
        core-admin workers remediate purity.no_ast_duplication --write

        # Just sense — populate blackboard, no LLM
        core-admin workers remediate purity.no_ast_duplication --sense-only
    """
    from body.workers.violation_remediator import ViolationRemediator
    from will.workers.audit_violation_sensor import AuditViolationSensor

    core_context: CoreContext = ctx.obj
    async with get_session() as session:
        await core_context.cognitive_service.initialize(session)
    mode = "SENSE-ONLY" if sense_only else "WRITE" if write else "DRY-RUN"
    logger.info(
        "[bold cyan]Remediation pipeline[/bold cyan] rule=[yellow]%s[/yellow] mode=[bold]%s[/bold]",
        rule,
        mode,
    )
    logger.info("\n[cyan]Step 1/2 — AuditViolationSensor[/cyan]")
    sensor = AuditViolationSensor(
        core_context=core_context,
        declaration_name=f"audit_sensor_{rule.split('.')[0]}",
        rule_namespace=rule,
        dry_run=not write,
    )
    await sensor.start()
    logger.info("[green]✓ Sensor complete.[/green]")
    if sense_only:
        logger.info(
            "\n[yellow]--sense-only: skipping remediator. Check blackboard for findings:[/yellow]"
        )
        logger.info(
            "  core-admin workers blackboard --filter 'audit.violation::%s'", rule
        )
        return
    logger.info("\n[cyan]Step 2/2 — ViolationRemediator[/cyan]")
    remediator = ViolationRemediator(
        core_context=core_context, target_rule=rule, write=write
    )
    await remediator.start()
    logger.info("[green]✓ Remediator complete.[/green]")
    console.print()
    if write:
        logger.info(
            "[bold green]Pipeline complete in WRITE mode.[/bold green]\nFixes applied and committed. Run audit to verify:"
        )
        logger.info("  core-admin code audit")
    else:
        logger.info(
            "[bold yellow]Pipeline complete in DRY-RUN mode.[/bold yellow]\nProposed fixes are on the blackboard. Review them:"
        )
        logger.info(
            "  core-admin workers blackboard --filter 'audit.remediation.dry_run'"
        )
        logger.info("\nWhen satisfied, apply with:")
        logger.info("  core-admin workers remediate %s --write", rule)
