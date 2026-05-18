# src/cli/resources/vectors/sync.py
"""Thin client over POST /v1/sync/vectors (ADR-058 D2)."""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("sync")
@command_meta(
    canonical_name="vectors.sync",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize constitutional documents to vector collections.",
    dangerous=True,
)
@core_command(requires_context=False, dangerous=True)
# ID: 558c245a-7663-4a87-bf2d-4e3c612498bd
async def sync_vectors(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes to Qdrant."),
    target: str = typer.Option(
        "all", "--target", "-t", help="Target: policies, patterns, or all"
    ),
) -> None:
    """Synchronize constitutional documents to vector collections."""
    _ = ctx
    console.print(
        f"[bold cyan]🧠 Vector Sync (Constitution): "
        f"{'WRITE' if write else 'DRY-RUN'}[/bold cyan]"
    )
    client = CoreApiClient()
    initial = await client.sync_vectors(write=write, target=target)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]❌ sync_vectors failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client.poll_sync_run(run_id)
    if final.get("status") != "completed":
        console.print(
            f"[red]❌ Vector sync failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(1)
    console.print("[green]✅ Vector sync completed[/green]")
