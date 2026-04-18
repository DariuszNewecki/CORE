# src/cli/commands/fix/audit.py
"""
Audit remediation command for the 'fix' CLI group.

This is the A2 autonomy interface: CORE fixes its own constitutional violations
by automatically remediating audit findings using deterministic patterns.

Provides:
- fix audit: Automatically fix audit findings

CONSTITUTIONAL ALIGNMENT:
- All fixes go through FileHandler (IntentGuard enforcement)
- Validation mandatory (must prove improvement)
- Evidence artifacts written for traceability
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
from pathlib import Path

import typer
from rich.table import Table

from body.self_healing.remediation_models import RemediationMode
from cli.utils import core_command
from shared.context import CoreContext
from will.self_healing.audit_remediation_service import AuditRemediationService

from . import console, fix_app


@fix_app.command("audit")
@core_command(dangerous=True, confirmation=True)
# ID: 02131c6f-4f7e-4141-a7c6-7f72b7392e9f
async def fix_audit_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Actually apply fixes (default: dry-run)"
    ),
    mode: str = typer.Option(
        "safe_only",
        "--mode",
        help="Risk tolerance: safe_only | medium_risk | all_deterministic",
    ),
    pattern: str = typer.Option(
        None,
        "--pattern",
        help="Only fix findings matching this pattern (e.g., 'style.*')",
    ),
    findings: Path = typer.Option(
        None,
        "--findings",
        help="Path to audit findings JSON (default: reports/audit_findings.processed.json)",
    ),
) -> None:
    """
    Autonomous remediation of audit findings.

    This command:
    1. Reads audit findings from reports/
    2. Matches findings to known fix patterns
    3. Executes deterministic fixes (NO LLM)
    4. Re-runs audit to validate improvement
    5. Writes evidence artifact

    Examples:
        # Dry-run: see what would be fixed
        core-admin fix audit

        # Actually fix safe violations
        core-admin fix audit --write

        # Only fix import issues
        core-admin fix audit --write --pattern "style.import*"

        # Use medium-risk fixes
        core-admin fix audit --write --mode medium_risk

    Modes:
        safe_only        - Only high-confidence (>85%), low-risk fixes
        medium_risk      - Include medium-confidence (>70%), medium-risk fixes
        all_deterministic - All non-LLM fixes (use with caution)
    """
    core_context: CoreContext = ctx.obj
    try:
        mode_enum = RemediationMode(mode)
    except ValueError:
        logger.info(
            "[red]Invalid mode: %s[/red]\nValid modes: safe_only, medium_risk, all_deterministic",
            mode,
        )
        raise typer.Exit(1)
    logger.info("\n[bold cyan]🔧 CORE Audit Remediation[/bold cyan]")
    logger.info("Mode: %s", mode_enum.value)
    logger.info(
        "Write: %s", "YES - Will modify files" if write else "NO - Dry run only"
    )
    if pattern:
        logger.info("Pattern filter: %s", pattern)
    console.print()
    service = AuditRemediationService(
        file_handler=core_context.file_handler,
        auditor_context=core_context.auditor_context,
        repo_root=core_context.git_service.repo_path,
    )
    with logger.info("[cyan]Running remediation...[/cyan]"):
        result = await service.remediate(
            findings_path=findings, mode=mode_enum, target_pattern=pattern, write=write
        )
    _display_results(result, write)
    if write and (not result.validation_passed):
        logger.info("\n[yellow]⚠️  Validation failed - no improvement detected[/yellow]")
        raise typer.Exit(1)


def _display_results(result, write: bool) -> None:
    """
    Display remediation results in a nice format.

    Args:
        result: RemediationResult object
        write: Whether this was a real run or dry-run
    """
    logger.info("\n[bold]📊 Remediation Summary[/bold]\n")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    summary_table.add_row("Total findings", str(result.total_findings))
    summary_table.add_row("Fixable patterns matched", str(len(result.matched_patterns)))
    summary_table.add_row("Not fixable (yet)", str(len(result.unmatched_findings)))
    summary_table.add_row("", "")
    summary_table.add_row("Fixes attempted", str(result.fixes_attempted))
    summary_table.add_row("Fixes succeeded", f"[green]{result.fixes_succeeded}[/green]")
    summary_table.add_row("Fixes failed", f"[red]{result.fixes_failed}[/red]")
    if write:
        summary_table.add_row("", "")
        summary_table.add_row("Findings before", str(result.findings_before))
        summary_table.add_row("Findings after", str(result.findings_after))
        delta_color = "green" if result.improvement_delta > 0 else "red"
        summary_table.add_row(
            "Improvement",
            f"[{delta_color}]{result.improvement_delta} fewer violations[/{delta_color}]",
        )
    logger.info(summary_table)
    if write:
        logger.info()
        if result.validation_passed:
            logger.info("[green]✅ Validation PASSED - Quality improved[/green]")
        else:
            logger.info("[red]❌ Validation FAILED - No improvement[/red]")
    if result.fix_details:
        logger.info("\n[bold]🔨 Fix Details[/bold]\n")
        fix_table = Table()
        fix_table.add_column("File", style="cyan", no_wrap=False)
        fix_table.add_column("Handler", style="magenta")
        fix_table.add_column("Status", style="white")
        fix_table.add_column("Duration", justify="right")
        for detail in result.fix_details[:10]:
            status_emoji = {"success": "✅", "failed": "❌", "skipped": "⏭️"}.get(
                detail.status, "?"
            )
            status_text = f"{status_emoji} {detail.status}"
            if detail.error_message and detail.status == "failed":
                status_text += f"\n[dim]{detail.error_message[:50]}[/dim]"
            fix_table.add_row(
                detail.file_path,
                detail.action_handler,
                status_text,
                f"{detail.duration_ms}ms",
            )
        logger.info(fix_table)
        if len(result.fix_details) > 10:
            logger.info("\n[dim]... and %s more[/dim]", len(result.fix_details) - 10)
    logger.info("\n[bold]📝 Evidence:[/bold] %s", result.remediation_output_path)
    if not write and result.fixes_attempted > 0:
        logger.info(
            "\n[bold yellow]💡 Tip:[/bold yellow] Run with [cyan]--write[/cyan] to apply these fixes"
        )
    console.print()
