# src/cli/resources/vectors/sync_code.py
"""Thin client over POST /v1/sync/code-vectors (ADR-058 D2)."""

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


@app.command("sync-code")
@command_meta(
    canonical_name="vectors.sync-code",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Synchronize codebase symbol embeddings.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=False)
# ID: 6489b6df-f2d8-4480-b0e2-e3054c9c11dc
async def sync_code_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Commit vectors to Qdrant."),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all symbols."
    ),
) -> None:
    """Synchronize codebase symbol embeddings with the vector database."""
    _ = ctx
    _ = force  # API doesn't currently expose a force flag; #361 follow-up.
    mode = "SYNCING" if write else "ANALYZING"
    console.print(f"[bold cyan]🧠 {mode} codebase vectors...[/bold cyan]")
    client = CoreApiClient()
    initial = await client.sync_code_vectors(write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]❌ sync_code_vectors failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client.poll_sync_run(run_id)
    if final.get("status") != "completed":
        console.print(
            f"[red]❌ Code vector sync failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(1)
    console.print("[green]✅ Code vector sync completed[/green]")
