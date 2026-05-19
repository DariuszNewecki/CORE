# src/cli/commands/fix/db_tools.py
"""
Database and vector-related commands for the 'fix' CLI group.

Thin clients over POST /v1/sync/knowledge-graph and POST /v1/sync/vectors
(ADR-058 D2). Both endpoints dispatch async; the CLI polls the
sync_runs resource until terminal.
"""

from __future__ import annotations

import logging

import typer

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)


@fix_app.command(
    "knowledge-graph",
    help="Synchronize code symbols to the PostgreSQL knowledge graph.",
)
@core_command(dangerous=True, confirmation=False, requires_context=False)
# ID: 40bd8310-f78e-43bd-bc79-21b3519bc802
async def sync_knowledge_graph_command(ctx: typer.Context) -> None:
    """Thin client over POST /v1/sync/knowledge-graph."""
    _ = ctx
    typer.secho("Syncing knowledge graph to database...", fg=typer.colors.CYAN)
    client = CoreApiClient()
    initial = await client.sync_knowledge_graph(write=True)
    run_id = initial.get("run_id")
    if not run_id:
        typer.secho(
            f"❌ sync_knowledge_graph failed to dispatch: {initial}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    final = await client.poll_sync_run(run_id)
    if final.get("status") != "completed":
        typer.secho(
            f"❌ Knowledge graph sync failed: {final.get('error') or final}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    typer.secho("✅ Knowledge graph sync completed", fg=typer.colors.GREEN)


@fix_app.command(
    "vector-sync", help="Atomically synchronize vectors between PostgreSQL and Qdrant."
)
@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: 945cd068-91ec-4e32-acd0-2e1be5148732
async def fix_vector_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply fixes to both PostgreSQL and Qdrant (otherwise dry-run).",
    ),
) -> None:
    """Atomic bidirectional vector synchronization via POST /v1/sync/vectors."""
    _ = ctx
    typer.secho("Synchronizing vector database...", fg=typer.colors.CYAN)
    client = CoreApiClient()
    initial = await client.sync_vectors(write=write)
    run_id = initial.get("run_id")
    if not run_id:
        typer.secho(
            f"❌ sync_vectors failed to dispatch: {initial}", fg=typer.colors.RED
        )
        raise typer.Exit(1)
    final = await client.poll_sync_run(run_id)
    if final.get("status") != "completed":
        typer.secho(
            f"❌ Vector synchronization failed: {final.get('error') or final}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    if write:
        typer.secho("✅ Vector synchronization completed", fg=typer.colors.GREEN)
    else:
        typer.secho(
            "✅ Vector synchronization dry-run completed", fg=typer.colors.GREEN
        )
