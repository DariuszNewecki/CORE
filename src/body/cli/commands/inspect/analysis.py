# src/body/cli/commands/inspect/analysis.py
# ID: body.cli.commands.inspect.analysis

"""
Code analysis commands.

Commands:
- inspect clusters - Semantic capability clusters
- inspect find-clusters - Deprecated alias
- inspect duplicates - Code duplication detection
- inspect common-knowledge - Consolidation opportunities
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.logic import diagnostics as diagnostics_logic
from body.cli.logic.duplicates import inspect_duplicates_async
from body.cli.logic.knowledge import find_common_knowledge
from shared.cli_utils import core_command, deprecated_command
from shared.context import CoreContext
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


console = Console()


@command_meta(
    canonical_name="inspect.clusters",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Finds and displays semantic capability clusters",
)
@core_command(dangerous=False)
# ID: 30d28d93-d6e8-4015-8525-c15dcde62654
async def clusters_cmd(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
) -> None:
    """
    Finds and displays semantic capability clusters.

    Examples:
        core-admin inspect clusters
        core-admin inspect clusters --n-clusters 50
    """
    core_context: CoreContext = ctx.obj
    clusters = await diagnostics_logic.find_clusters_logic(core_context, n_clusters)

    if not clusters:
        console.print("[yellow]No clusters found.[/yellow]")
        return

    console.print(f"[green]Found {len(clusters)} clusters:[/green]")
    for cluster in clusters:
        console.print(
            f"- {cluster.get('topic', 'Unknown')}: {cluster.get('size', 0)} items"
        )


@command_meta(
    canonical_name="inspect.find-clusters",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="DEPRECATED alias for 'inspect clusters'",
    aliases=["clusters"],
)
@core_command(dangerous=False)
# ID: ccaa2ab1-d8f3-4bc1-a108-9c0eccfca2e3
async def find_clusters_cmd(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
) -> None:
    """
    DEPRECATED alias for `inspect clusters`.

    Use: core-admin inspect clusters
    """
    deprecated_command("inspect find-clusters", "inspect clusters")
    await clusters_cmd(ctx, n_clusters=n_clusters)


@command_meta(
    canonical_name="inspect.duplicates",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    summary="Runs semantic code duplication check",
)
@core_command(dangerous=False)
# ID: 7c631dca-5259-4d2f-9ee8-676a48ec83c2
async def duplicates_command(
    ctx: typer.Context,
    threshold: float = typer.Option(
        0.80,
        "--threshold",
        "-t",
        help="The minimum similarity score to consider a duplicate.",
        min=0.5,
        max=1.0,
    ),
) -> None:
    """
    Runs only the semantic code duplication check.

    Examples:
        core-admin inspect duplicates
        core-admin inspect duplicates --threshold 0.9
    """
    core_context: CoreContext = ctx.obj
    await inspect_duplicates_async(context=core_context, threshold=threshold)


@command_meta(
    canonical_name="inspect.common-knowledge",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Finds structurally identical helper functions that can be consolidated",
)
@core_command(dangerous=False)
# ID: 349ae9d0-bd40-40a5-ab31-9f231db2b1c2
async def common_knowledge_cmd(ctx: typer.Context) -> None:
    """
    Finds structurally identical helper functions that can be consolidated.

    This helps identify DRY violations where the same logic is implemented
    multiple times across the codebase.

    Examples:
        core-admin inspect common-knowledge
    """
    await find_common_knowledge()


# Export commands for registration
analysis_commands = [
    {"name": "clusters", "func": clusters_cmd},
    {"name": "find-clusters", "func": find_clusters_cmd},
    {"name": "duplicates", "func": duplicates_command},
    {"name": "common-knowledge", "func": common_knowledge_cmd},
]
