# src/cli/commands/fix/audit.py
"""Audit remediation command for the 'fix' CLI group.

Thin client over POST /v1/audit/remediations (ADR-057 D4). The CLI
dispatches an audit_run_id + mode + write flag and polls the
audit_remediation_runs lifecycle. All remediation logic runs server-side.
"""

from __future__ import annotations

import logging

import typer
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command

from . import console, fix_app


logger = logging.getLogger(__name__)


# The CLI accepts both the long-form RemediationMode value names
# (safe_only / medium_risk / all_deterministic) and the wire-format names
# the API expects (safe / medium / all). Long-form names are translated.
_MODE_TO_WIRE = {
    "safe": "safe",
    "medium": "medium",
    "all": "all",
    "safe_only": "safe",
    "medium_risk": "medium",
    "all_deterministic": "all",
}


@fix_app.command("audit")
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: 02131c6f-4f7e-4141-a7c6-7f72b7392e9f
async def fix_audit_command(
    ctx: typer.Context,
    audit_run_id: str = typer.Option(
        ...,
        "--audit-run-id",
        help="UUID of the audit_runs row whose findings should be remediated.",
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually apply fixes (default: dry-run)"
    ),
    mode: str = typer.Option(
        "safe",
        "--mode",
        help="Risk tolerance: safe | medium | all (long-form: safe_only / medium_risk / all_deterministic).",
    ),
) -> None:
    """Autonomous remediation of audit findings via /v1/audit/remediations.

    Examples:
        # Dry-run — see what would be fixed
        core-admin fix audit --audit-run-id <uuid>

        # Apply safe fixes
        core-admin fix audit --audit-run-id <uuid> --write

        # Apply medium-risk fixes
        core-admin fix audit --audit-run-id <uuid> --write --mode medium
    """
    _ = ctx
    wire_mode = _MODE_TO_WIRE.get(mode)
    if wire_mode is None:
        console.print(
            f"[red]Invalid mode: {mode}[/red]\n"
            "Valid modes: safe, medium, all "
            "(long-form aliases: safe_only, medium_risk, all_deterministic)"
        )
        raise typer.Exit(1)

    console.print("\n[bold cyan]🔧 CORE Audit Remediation[/bold cyan]")
    console.print(f"Audit run: {audit_run_id}")
    console.print(f"Mode: {wire_mode}")
    console.print(
        f"Write: {'YES - Will modify files' if write else 'NO - Dry run only'}"
    )
    console.print()

    client = CoreApiClient()
    initial = await client.audit_remediate(
        audit_run_id=audit_run_id, mode=wire_mode, write=write
    )
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]❌ audit_remediate failed to dispatch: {initial}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[dim]Dispatched run {run_id} — polling…[/dim]")
    final = await client.poll_audit_remediation_run(run_id)
    if final.get("status") != "completed":
        console.print(
            f"[red]❌ Remediation failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(code=1)

    _display_results(final.get("result") or {}, write=write)


def _display_results(result: dict, *, write: bool) -> None:
    """Display remediation results in a Rich table."""
    console.print("\n[bold]📊 Remediation Summary[/bold]\n")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    summary_table.add_row("Total findings", str(result.get("total_findings", 0)))
    summary_table.add_row("Fixes attempted", str(result.get("fixes_attempted", 0)))
    summary_table.add_row(
        "Fixes succeeded",
        f"[green]{result.get('fixes_succeeded', 0)}[/green]",
    )
    if write:
        summary_table.add_row("", "")
        summary_table.add_row("Findings before", str(result.get("findings_before", 0)))
        summary_table.add_row("Findings after", str(result.get("findings_after", 0)))
        delta = int(result.get("improvement_delta", 0))
        delta_color = "green" if delta > 0 else "red"
        summary_table.add_row(
            "Improvement",
            f"[{delta_color}]{delta} fewer violations[/{delta_color}]",
        )
    console.print(summary_table)

    if write:
        if result.get("validation_passed"):
            console.print("[green]✅ Validation PASSED - Quality improved[/green]")
        else:
            console.print("[red]❌ Validation FAILED - No improvement[/red]")

    output_path = result.get("remediation_output_path")
    if output_path:
        console.print(f"\n[bold]📝 Evidence:[/bold] {output_path}")

    if not write and result.get("fixes_attempted", 0) > 0:
        console.print(
            "\n[bold yellow]💡 Tip:[/bold yellow] Run with [cyan]--write[/cyan] "
            "to apply these fixes"
        )
    console.print()
