# src/cli/commands/inspect/analysis.py
"""Code analysis commands.

Thin clients over /v1/analysis/{clusters,duplicates,common-knowledge}
(ADR-057 D3). Rendering stays inline.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)


logger = logging.getLogger(__name__)
console = Console()


@command_meta(
    canonical_name="inspect.clusters",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Finds and displays semantic capability clusters",
)
@core_command(dangerous=False, requires_context=False)
# ID: 9c6d2c21-ed6b-4bf0-bbf2-d02b5a8a9d72
async def clusters_cmd(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
) -> None:
    """Finds and displays semantic capability clusters."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.analysis_clusters(limit=n_clusters)
    if not payload.get("available", True):
        console.print("[yellow]Cluster inspector not available on the server.[/yellow]")
        return
    clusters = payload.get("clusters") or []
    if not clusters:
        console.print("[yellow]No clusters found.[/yellow]")
        return
    console.print(f"[green]Found {len(clusters)} clusters:[/green]")
    for cluster in clusters:
        topic = (
            cluster.get("topic", "Unknown")
            if isinstance(cluster, dict)
            else str(cluster)
        )
        size = cluster.get("size", 0) if isinstance(cluster, dict) else ""
        console.print(f"- {topic}: {size} items")


@command_meta(
    canonical_name="inspect.duplicates",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Runs semantic code duplication check",
)
@core_command(dangerous=False, requires_context=False)
# ID: cb72e5c2-4233-4de3-b784-4a3bf02ff34d
async def duplicates_command(
    ctx: typer.Context,
    threshold: float = typer.Option(
        0.8,
        "--threshold",
        "-t",
        help="The minimum similarity score to consider a duplicate.",
        min=0.5,
        max=1.0,
    ),
) -> None:
    """Runs the semantic code duplication check via the API."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.analysis_duplicates(threshold=threshold)
    if not payload.get("ok", False):
        console.print(
            f"[red]Duplicates analysis failed: {payload.get('error', 'unknown')}[/red]"
        )
        raise typer.Exit(code=1)
    note = payload.get("note")
    if note:
        console.print(f"[dim]{note}[/dim]")
    console.print(
        f"[green]✅ Duplicates check completed at threshold {threshold}.[/green]"
    )


@command_meta(
    canonical_name="inspect.common-knowledge",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Finds structurally identical helper functions that can be consolidated",
)
@core_command(dangerous=False, requires_context=False)
# ID: 508b7556-2747-4822-8772-7a354bd82760
async def common_knowledge_cmd(ctx: typer.Context) -> None:
    """Finds DRY-violation candidates via /v1/analysis/common-knowledge."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.analysis_common_knowledge()
    if not payload.get("available", True):
        console.print(
            "[yellow]Common-knowledge inspector not available on the server.[/yellow]"
        )
        return
    candidates = payload.get("candidates") or []
    if not candidates:
        console.print("[green]No DRY-violation candidates found.[/green]")
        return
    table = Table(title=f"DRY Candidates ({len(candidates)})")
    table.add_column("Candidate", style="cyan")
    table.add_column("Occurrences", justify="right")
    for candidate in candidates:
        if isinstance(candidate, dict):
            table.add_row(
                str(candidate.get("symbol", candidate.get("id", ""))),
                str(candidate.get("occurrences", "")),
            )
        else:
            table.add_row(str(candidate), "")
    console.print(table)


analysis_commands = [
    {"name": "clusters", "func": clusters_cmd},
    {"name": "duplicates", "func": duplicates_command},
    {"name": "common-knowledge", "func": common_knowledge_cmd},
]
