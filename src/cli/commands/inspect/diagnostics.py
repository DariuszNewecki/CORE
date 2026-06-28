# src/cli/commands/inspect/diagnostics.py
"""System diagnostics commands.

Thin clients over /v1/analysis/{command-tree,test-targets} (ADR-057 D3).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

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
    canonical_name="inspect.command-tree",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Displays a hierarchical tree view of all available CLI commands",
)
@core_command(dangerous=False, requires_context=False)
# ID: d7718166-cf0c-4ec3-b6e5-9f4804d56d1b
async def command_tree_cmd(ctx: typer.Context) -> None:
    """Display the CLI command hierarchy served by the API."""
    _ = ctx
    console.print("Building CLI Command Tree...")
    client = CoreApiClient()
    payload = await client.analysis_command_tree()
    if not payload.get("available", True):
        console.print(
            f"[yellow]Command-tree backend unavailable: "
            f"{payload.get('error', 'unknown')}[/yellow]"
        )
        return

    tree_data = payload.get("commands") or []
    root = Tree("[bold blue]CORE CLI[/bold blue]")

    # ID: 642514fc-30cb-4d57-b3fd-8f0b2461e77c
    def add_nodes(nodes: list[dict[str, Any]], parent: Tree) -> None:
        """Recursively add nodes to the Rich tree."""
        for node in nodes:
            label = f"[bold]{node['name']}[/bold]"
            if node.get("help"):
                label += f": [dim]{node['help']}[/dim]"
            branch = parent.add(label)
            children = node.get("children")
            if children:
                add_nodes(children, branch)

    add_nodes(tree_data, root)
    console.print(root)


@command_meta(
    canonical_name="inspect.test-targets",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Identifies and classifies functions as SIMPLE or COMPLEX test targets",
)
@core_command(dangerous=False, requires_context=False)
# ID: ab41749f-0338-49c3-8a1e-9812a4f1b3a2
async def inspect_test_targets(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="The path to the Python file to analyze.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """Classify functions as SIMPLE or COMPLEX test targets via the API."""
    _ = ctx
    _ = file_path  # /v1/analysis/test-targets scans the canonical src/ tree.
    client = CoreApiClient()
    payload = await client.analysis_test_targets()
    if not payload.get("available", True):
        console.print(
            f"[yellow]Test-target classifier unavailable: "
            f"{payload.get('error', 'unknown')}[/yellow]"
        )
        return

    targets = payload.get("targets") or []
    if not targets:
        console.print("[yellow]No suitable public functions found to analyze.[/yellow]")
        return

    table = Table(
        title="Test Target Analysis", header_style="bold magenta", show_header=True
    )
    table.add_column("Function", style="cyan")
    table.add_column("Complexity", style="magenta", justify="right")
    table.add_column("Classification", style="yellow")
    table.add_column("Reason")
    for target in targets:
        if not isinstance(target, dict):
            continue
        classification = str(target.get("classification", ""))
        style = "green" if classification == "SIMPLE" else "red"
        table.add_row(
            str(target.get("name", "")),
            str(target.get("complexity", "")),
            f"[{style}]{classification}[/{style}]",
            str(target.get("reason", "")),
        )
    console.print(table)


diagnostics_commands = [
    {"name": "command-tree", "func": command_tree_cmd},
    {"name": "test-targets", "func": inspect_test_targets},
]
