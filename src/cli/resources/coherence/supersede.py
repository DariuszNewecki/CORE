# src/cli/resources/coherence/supersede.py
"""
`core-admin coherence supersede` — retire one CCC run by supersession from a
canonical run. Bulk-dismisses every unreviewed candidate in the old run
with a mandatory note, closes the old run, then recomputes the canonical
run's denormalized ``unreviewed_count``.

Governing ADR: .specs/decisions/ADR-067-constitutional-coherence-checker.md (D6).
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from body.services.coherence_service import CoherenceService
from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("supersede")
@core_command(dangerous=True, requires_context=False)
# ID: 1679b214-2bda-45f1-a28a-2e5080efeb02
async def supersede_command(
    old_run_id: str = typer.Argument(
        ...,
        help="Run id to retire (must be currently open).",
    ),
    by: str = typer.Option(
        ...,
        "--by",
        help="Canonical run id that supersedes the old run.",
    ),
    note: str = typer.Option(
        ...,
        "--note",
        help=(
            "Mandatory rationale recorded on every dismissed candidate's "
            "triage_note. The supersession is auditable through ordinary "
            "triage history."
        ),
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the interactive confirmation prompt.",
    ),
) -> None:
    """Retire one CCC run by supersession from another."""
    if not note.strip():
        console.print("[red]X --note must not be empty.[/red]")
        raise typer.Exit(code=1)

    async with get_session() as session:
        service = CoherenceService(session)

        old_run = await service.get_run(old_run_id)
        canonical_run = await service.get_run(by)

        if old_run is None:
            console.print(f"[red]X old_run_id not found: {old_run_id}[/red]")
            raise typer.Exit(code=1)
        if canonical_run is None:
            console.print(f"[red]X --by canonical_run_id not found: {by}[/red]")
            raise typer.Exit(code=1)
        if old_run["run_status"] != "open":
            console.print(
                f"[red]X old_run_id {old_run_id} is not open "
                f"(status: {old_run['run_status']}).[/red]"
            )
            raise typer.Exit(code=1)

        dismiss_preview = int(old_run.get("unreviewed_count") or 0)
        age_warning = canonical_run["run_at"] <= old_run["run_at"]

        console.print(
            f"[bold]Supersede preview:[/bold] {dismiss_preview} unreviewed "
            f"candidate(s) in run [cyan]{old_run_id[:8]}[/cyan] will be "
            f"dismissed and the run closed. Canonical "
            f"[cyan]{by[:8]}[/cyan]'s denormalized count will be repaired."
        )
        if age_warning:
            console.print(
                f"[yellow]! Canonical run_at ({canonical_run['run_at']}) is "
                f"not newer than old run_at ({old_run['run_at']}). "
                f"Proceeding because --note records the rationale.[/yellow]"
            )

        if not yes:
            confirmed = typer.confirm("Apply?", default=False)
            if not confirmed:
                console.print("[yellow]Aborted by governor.[/yellow]")
                raise typer.Exit(code=1)

        try:
            result = await service.supersede_run(
                old_run_id=old_run_id,
                canonical_run_id=by,
                note=note,
            )
        except ValueError as exc:
            console.print(f"[red]X supersede failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc
        except Exception as exc:
            logger.exception("supersede failed")
            console.print(f"[red]X supersede failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    console.print(
        f"[green]Supersede complete:[/green] "
        f"{result['dismissed_count']} candidate(s) dismissed; "
        f"run [cyan]{old_run_id[:8]}[/cyan] closed; canonical "
        f"[cyan]{by[:8]}[/cyan] count "
        f"{result['canonical_old_count']} -> {result['canonical_new_count']}."
    )
