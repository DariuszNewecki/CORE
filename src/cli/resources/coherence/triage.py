# src/cli/resources/coherence/triage.py
"""
`core-admin coherence triage` — record a triage decision on one CCC candidate.

Governing ADR: .specs/decisions/ADR-067-constitutional-coherence-checker.md (D2).
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


_ALLOWED_DECISIONS = ("confirmed", "dismissed", "deferred")


@app.command("triage")
@core_command(dangerous=True, requires_context=False)
# ID: a8fe052f-0103-4b62-a2cb-eaadc5a368d8
async def triage_command(
    candidate_id: str = typer.Argument(..., help="Candidate id to triage."),
    decision: str = typer.Argument(
        ...,
        help=f"Triage decision: one of {', '.join(_ALLOWED_DECISIONS)}.",
    ),
    note: str = typer.Option(
        None,
        "--note",
        help="Governor rationale. Required when DECISION is 'dismissed'.",
    ),
) -> None:
    """Record a triage decision on one candidate."""
    decision_normalized = decision.strip().lower()
    if decision_normalized not in _ALLOWED_DECISIONS:
        console.print(
            f"[red]❌ Invalid decision '{decision}'. "
            f"Must be one of: {', '.join(_ALLOWED_DECISIONS)}.[/red]"
        )
        raise typer.Exit(code=1)

    if decision_normalized == "dismissed" and not note:
        console.print("[red]❌ --note is required when DECISION is 'dismissed'.[/red]")
        raise typer.Exit(code=1)

    async with get_session() as session:
        service = CoherenceService(session)
        try:
            result = await service.triage_candidate(
                candidate_id=candidate_id,
                decision=decision_normalized,
                note=note,
            )
        except Exception as exc:
            logger.exception("Triage failed")
            console.print(f"[red]❌ Triage failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc

    if result["run_id"] is None:
        console.print(f"[red]❌ Candidate not found: {candidate_id}[/red]")
        raise typer.Exit(code=1)

    console.print(
        f"[green]✅ Candidate {candidate_id} marked {decision_normalized}.[/green]"
    )
    if result["run_closed"]:
        console.print(
            f"[bold green]Run {result['run_id']} closed — "
            f"all candidates triaged.[/bold green]"
        )
