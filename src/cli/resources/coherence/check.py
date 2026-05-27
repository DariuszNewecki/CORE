# src/cli/resources/coherence/check.py
"""
`core-admin coherence check` — trigger a Constitutional Coherence Checker run.

Governing ADR: .specs/decisions/ADR-067-constitutional-coherence-checker.md (D2).
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from body.services.coherence_service import CoherenceService
from cli.utils import core_command
from mind.coherence.checker import CoherenceChecker
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("check")
@core_command(dangerous=True, requires_context=True)
# ID: 02507f9f-3bdc-41d8-b9af-982b0411ce37
async def check_command(
    ctx: typer.Context,
    full: bool = typer.Option(
        False,
        "--full",
        help=(
            "Evaluate the full corpus regardless of prior runs. Required for "
            "the first run on any installation. Without --full, trigger is "
            "auto-detected from the previous run's input_manifest."
        ),
    ),
    sample: int = typer.Option(
        None,
        "--sample",
        help=(
            "Randomly sample N rule files for R2/R3 (R1 still scans all "
            "ADRs). Use for narrow exploratory runs. Omit to evaluate all "
            "rule files."
        ),
    ),
) -> None:
    """Run one Constitutional Coherence Checker pass — 7 check classes per ADR-073."""
    context: CoreContext = ctx.obj
    try:
        cognitive_service = await context.registry.get_cognitive_service()
    except Exception as exc:
        logger.exception("Failed to acquire CognitiveService")
        console.print(f"[red]❌ Cognitive service unavailable: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    async with get_session() as session:
        coherence_service = CoherenceService(session)
        checker = CoherenceChecker(
            cognitive_service=cognitive_service,
            coherence_service=coherence_service,
            repo_root=settings.REPO_PATH,
        )

        console.print("[cyan]Starting coherence run…[/cyan]")
        try:
            run_id = await checker.run(full=full, sample_rules=sample)
        except Exception as exc:
            logger.exception("Coherence run failed")
            console.print(f"[red]❌ Coherence run failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc

        console.print(f"Run started: {run_id}")

        run = await coherence_service.get_run(run_id)

    if run is None:
        console.print("[yellow]Run row not found after completion.[/yellow]")
        raise typer.Exit(code=1)

    manifest = run.get("input_manifest") or []
    checked = sum(1 for e in manifest if e.get("status") == "checked")
    skipped = sum(1 for e in manifest if e.get("status") == "skipped")
    candidates = int(run.get("candidate_count") or 0)

    console.print(
        f"[green]Coverage:[/green] {checked} checked, {skipped} skipped "
        f"· [bold]Candidates:[/bold] {candidates} produced"
    )

    total = checked + skipped
    if total > 0 and skipped / total > 0.20:
        console.print(
            f"[yellow]⚠ WARNING: {skipped}/{total} input items skipped "
            f"({skipped / total:.0%}). See `core-admin coherence report` for "
            f"per-item skipped_reason.[/yellow]"
        )
