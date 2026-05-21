# src/cli/resources/coherence/report.py
"""
`core-admin coherence report` — display a Constitutional Coherence Report.

Governing ADR: .specs/decisions/ADR-067-constitutional-coherence-checker.md (D2).
"""

from __future__ import annotations

import logging
from collections import Counter

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from body.services.coherence_service import CoherenceService
from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


_CLAIM_TRUNCATE = 80
_TRIAGE_COLORS = {
    "unreviewed": "yellow",
    "confirmed": "red",
    "dismissed": "dim",
    "deferred": "cyan",
}


@app.command("report")
@core_command(dangerous=False, requires_context=False)
# ID: ef0a593c-f8b4-4398-ab1e-369086501481
async def report_command(
    run_id: str = typer.Argument(
        None,
        help="Run id to report on. Omit to use the most recent run.",
    ),
) -> None:
    """Display the Constitutional Coherence Report for a run."""
    async with get_session() as session:
        service = CoherenceService(session)
        try:
            run = (
                await service.get_run(run_id)
                if run_id
                else await service.get_latest_run()
            )
        except Exception as exc:
            logger.exception("Failed to load coherence run")
            console.print(f"[red]❌ Failed to load run: {exc}[/red]")
            raise typer.Exit(code=1) from exc

        if run is None:
            console.print(
                "[yellow]No coherence runs recorded. Run "
                "`core-admin coherence check --full` to create one.[/yellow]"
            )
            return

        candidates = await service.get_candidates(run["run_id"])

    _render_metadata(run)
    _render_manifest(run.get("input_manifest") or [])
    _render_candidates(candidates)
    _render_triage_summary(candidates)


def _render_metadata(run: dict) -> None:
    grid = Table.grid(expand=False, padding=(0, 1))
    grid.add_row("run_id:", run["run_id"])
    grid.add_row("run_at:", str(run["run_at"]))
    grid.add_row("trigger:", run["trigger"])
    status_color = "green" if run["run_status"] == "closed" else "yellow"
    grid.add_row("status:", f"[{status_color}]{run['run_status']}[/{status_color}]")
    grid.add_row(
        "counts:",
        f"{run['candidate_count']} candidate(s) · {run['unreviewed_count']} unreviewed",
    )
    console.print(Panel(grid, title="Coherence Run", expand=False))


def _render_manifest(manifest: list[dict]) -> None:
    if not manifest:
        console.print("[dim]Manifest is empty.[/dim]")
        return
    table = Table(title="Coverage Manifest", expand=True)
    table.add_column("path", style="cyan", no_wrap=True)
    table.add_column("domain", style="magenta")
    table.add_column("status", justify="center")
    table.add_column("skipped_reason", style="dim")
    for entry in manifest:
        status = entry.get("status", "unknown")
        status_color = "green" if status == "checked" else "yellow"
        table.add_row(
            str(entry.get("path", "")),
            str(entry.get("domain", "")),
            f"[{status_color}]{status}[/{status_color}]",
            str(entry.get("skipped_reason") or ""),
        )
    console.print(table)


def _render_candidates(candidates: list[dict]) -> None:
    if not candidates:
        console.print("[dim]No candidates produced.[/dim]")
        return
    table = Table(title="Candidates", expand=True)
    table.add_column("candidate_id", style="cyan", no_wrap=True)
    table.add_column("relation", justify="center")
    table.add_column("claim")
    table.add_column("triage", justify="center")
    for c in candidates:
        claim = c.get("claim") or ""
        if len(claim) > _CLAIM_TRUNCATE:
            claim = claim[: _CLAIM_TRUNCATE - 1] + "…"
        decision = c.get("triage_decision", "unreviewed")
        color = _TRIAGE_COLORS.get(decision, "white")
        table.add_row(
            c["candidate_id"],
            c.get("relation", ""),
            claim,
            f"[{color}]{decision}[/{color}]",
        )
    console.print(table)


def _render_triage_summary(candidates: list[dict]) -> None:
    counts = Counter(c.get("triage_decision", "unreviewed") for c in candidates)
    summary = Table.grid(expand=False, padding=(0, 1))
    summary.add_row(
        f"[red]{counts.get('confirmed', 0)}[/red] confirmed",
        f"[dim]{counts.get('dismissed', 0)}[/dim] dismissed",
        f"[cyan]{counts.get('deferred', 0)}[/cyan] deferred",
        f"[yellow]{counts.get('unreviewed', 0)}[/yellow] unreviewed",
    )
    console.print(Panel(summary, title="Triage Summary", expand=False))
