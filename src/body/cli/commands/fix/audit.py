# src/body/cli/commands/fix/audit.py
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

from pathlib import Path

import typer
from rich.table import Table

from features.self_healing.audit_remediation_service import AuditRemediationService
from features.self_healing.remediation_models import RemediationMode
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext

# Import from local fix module hub
from . import console, fix_app


@fix_app.command("audit")
@core_command(dangerous=True, confirmation=True)
# ID: dac5dfbd-9734-4fb4-bfc3-b6788e3dea96
# ID: 5baef0d6-3323-4486-b95b-b9caf10d16f7
async def fix_audit_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Actually apply fixes (default: dry-run)",
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

    # Get CoreContext from typer
    core_context: CoreContext = ctx.obj

    # Validate mode
    try:
        mode_enum = RemediationMode(mode)
    except ValueError:
        console.print(
            f"[red]Invalid mode: {mode}[/red]\n"
            f"Valid modes: safe_only, medium_risk, all_deterministic"
        )
        raise typer.Exit(1)

    # Show what we're about to do
    console.print("\n[bold cyan]🔧 CORE Audit Remediation[/bold cyan]")
    console.print(f"Mode: {mode_enum.value}")
    console.print(
        f"Write: {'YES - Will modify files' if write else 'NO - Dry run only'}"
    )
    if pattern:
        console.print(f"Pattern filter: {pattern}")
    console.print()

    # Create the service
    service = AuditRemediationService(
        file_handler=core_context.file_handler,
        auditor_context=core_context.auditor_context,
        repo_root=settings.REPO_PATH,
    )

    # Run remediation
    with console.status("[cyan]Running remediation...[/cyan]"):
        result = await service.remediate(
            findings_path=findings,
            mode=mode_enum,
            target_pattern=pattern,
            write=write,
        )

    # Display results
    _display_results(result, write)

    # Exit code based on success
    if write and not result.validation_passed:
        console.print(
            "\n[yellow]⚠️  Validation failed - no improvement detected[/yellow]"
        )
        raise typer.Exit(1)


def _display_results(result, write: bool) -> None:
    """
    Display remediation results in a nice format.

    Args:
        result: RemediationResult object
        write: Whether this was a real run or dry-run
    """

    console.print("\n[bold]📊 Remediation Summary[/bold]\n")

    # Create summary table
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Total findings", str(result.total_findings))
    summary_table.add_row("Fixable patterns matched", str(len(result.matched_patterns)))
    summary_table.add_row("Not fixable (yet)", str(len(result.unmatched_findings)))
    summary_table.add_row("", "")  # Spacer
    summary_table.add_row("Fixes attempted", str(result.fixes_attempted))
    summary_table.add_row("Fixes succeeded", f"[green]{result.fixes_succeeded}[/green]")
    summary_table.add_row("Fixes failed", f"[red]{result.fixes_failed}[/red]")

    if write:
        summary_table.add_row("", "")  # Spacer
        summary_table.add_row("Findings before", str(result.findings_before))
        summary_table.add_row("Findings after", str(result.findings_after))

        delta_color = "green" if result.improvement_delta > 0 else "red"
        summary_table.add_row(
            "Improvement",
            f"[{delta_color}]{result.improvement_delta} fewer violations[/{delta_color}]",
        )

    console.print(summary_table)

    # Validation status
    if write:
        console.print()
        if result.validation_passed:
            console.print("[green]✅ Validation PASSED - Quality improved[/green]")
        else:
            console.print("[red]❌ Validation FAILED - No improvement[/red]")

    # Show fix details if there were any
    if result.fix_details:
        console.print("\n[bold]🔨 Fix Details[/bold]\n")

        fix_table = Table()
        fix_table.add_column("File", style="cyan", no_wrap=False)
        fix_table.add_column("Handler", style="magenta")
        fix_table.add_column("Status", style="white")
        fix_table.add_column("Duration", justify="right")

        for detail in result.fix_details[:10]:  # Show first 10
            status_emoji = {
                "success": "✅",
                "failed": "❌",
                "skipped": "⏭️",
            }.get(detail.status, "?")

            status_text = f"{status_emoji} {detail.status}"
            if detail.error_message and detail.status == "failed":
                status_text += f"\n[dim]{detail.error_message[:50]}[/dim]"

            fix_table.add_row(
                detail.file_path,
                detail.action_handler,
                status_text,
                f"{detail.duration_ms}ms",
            )

        console.print(fix_table)

        if len(result.fix_details) > 10:
            console.print(f"\n[dim]... and {len(result.fix_details) - 10} more[/dim]")

    # Evidence location
    console.print(f"\n[bold]📝 Evidence:[/bold] {result.remediation_output_path}")

    # Suggest next steps
    if not write and result.fixes_attempted > 0:
        console.print(
            "\n[bold yellow]💡 Tip:[/bold yellow] Run with [cyan]--write[/cyan] to apply these fixes"
        )

    console.print()
