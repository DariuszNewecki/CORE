# src/cli/commands/run.py
"""
Commands for executing specific complex system processes.

`vectorize` is a thin client over POST /v1/sync/code-vectors (ADR-058 D2).
The constitutional worker pipeline (`RepoCrawlerWorker` +
`RepoEmbedderWorker`) runs server-side; this CLI polls the sync_runs
resource until terminal.
"""

from __future__ import annotations

import logging

import typer

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles.",
    no_args_is_help=True,
)


@run_app.command("vectorize")
@core_command(dangerous=True, requires_context=False)
# ID: f8e9d0a1-b2c3-4d5e-6f7a-8b9c0d1e2f3a
async def vectorize_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Commit vectors to Qdrant."),
    force: bool = typer.Option(
        False, help="Force re-vectorization of all capabilities."
    ),
):
    """Vectorize codebase artifacts via the constitutional worker pipeline."""
    _ = ctx
    _ = force  # API doesn't currently expose a force flag; #361 follow-up.
    typer.secho(
        "🚀 Starting vectorization via constitutional worker pipeline...",
        fg=typer.colors.CYAN,
    )
    client = CoreApiClient()
    initial = await client.sync_code_vectors(write=write)
    run_id = initial.get("run_id")
    if not run_id:
        typer.secho(
            f"❌ sync_code_vectors failed to dispatch: {initial}", fg=typer.colors.RED
        )
        raise typer.Exit(1)
    final = await client.poll_sync_run(run_id)
    if final.get("status") != "completed":
        typer.secho(
            f"❌ Vectorization failed: {final.get('error') or final}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    typer.secho("✅ Vectorization completed", fg=typer.colors.GREEN)
