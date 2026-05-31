# src/cli/resources/coherence/repair_counts.py
"""
`core-admin coherence repair-counts` — recompute the denormalized
``unreviewed_count`` on every open coherence run from live candidate state.

Governing ADR: .specs/decisions/ADR-067-constitutional-coherence-checker.md (D6).
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from body.services.coherence_service import CoherenceService
from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("repair-counts")
@core_command(dangerous=True, requires_context=False)
# ID: a7f3ef25-a40c-46b9-8f6a-029acb69ffab
async def repair_counts_command() -> None:
    """Recompute unreviewed_count from live triage state across all open runs."""
    async with get_session() as session:
        service = CoherenceService(session)
        try:
            deltas = await service.repair_unreviewed_counts()
        except Exception as exc:
            logger.exception("repair-counts failed")
            console.print(f"[red]X repair-counts failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    if not deltas:
        console.print("[green]No open runs — nothing to repair.[/green]")
        return

    table = Table(title="Coherence repair-counts — per-run delta")
    table.add_column("run_id", style="cyan", no_wrap=True)
    table.add_column("old", justify="right")
    table.add_column("new", justify="right")
    table.add_column("delta", justify="right")
    table.add_column("closed?")

    drift_total = 0
    closed_total = 0
    for d in deltas:
        delta_n = d["new_count"] - d["old_count"]
        drift_total += abs(delta_n)
        if d["closed"]:
            closed_total += 1
        delta_str = f"{delta_n:+d}" if delta_n != 0 else "0"
        table.add_row(
            d["run_id"][:8],
            str(d["old_count"]),
            str(d["new_count"]),
            delta_str,
            "yes" if d["closed"] else "no",
        )

    console.print(table)
    console.print(
        f"[bold]Drift repaired:[/bold] {drift_total} row(s) across "
        f"{len(deltas)} run(s); [bold]auto-closed:[/bold] {closed_total}."
    )
