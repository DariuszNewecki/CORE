# src/body/cli/commands/diagnostics.py

"""
Diagnostic Command Group.

Compliance:
- command_patterns.yaml: Inspect Pattern (output to stdout, --format support).
- logging_standards.yaml: Use print()/rich only in CLI entry points.

Golden-path adjustments (Phase 1, non-breaking):
- Deprecated: `diagnostics find-clusters` -> `inspect clusters`
- Deprecated: `diagnostics command-tree` -> `inspect command-tree`
  (machine-readable formats json/yaml remain supported here until inspect adds --format)
"""

from __future__ import annotations

import json
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.tree import Tree

from body.cli.logic import diagnostics as logic
from body.cli.logic.diagnostics_policy import policy_coverage
from body.cli.logic.diagnostics_registry import (
    check_legacy_tags,
    cli_registry,
    manifest_hygiene,
)
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
app = typer.Typer(help="Deep diagnostic and integrity checks.")
console = Console()


def _deprecated(old: str, new: str) -> None:
    typer.secho(
        f"DEPRECATED: '{old}' -> use '{new}'",
        fg=typer.colors.YELLOW,
    )


@app.command("find-clusters")
@core_command()
# ID: 91856850-423f-4c27-90c3-e06f56a3841a
async def find_clusters_command(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="Number of clusters."
    ),
    format: str = typer.Option("table", "--format", help="Output format (table|json)"),
) -> None:
    """
    DEPRECATED alias for `inspect clusters`.

    Notes:
    - `inspect clusters` is canonical in the golden tree.
    - We keep `--format json` here for backwards-compatible machine output.
    """
    _deprecated("diagnostics find-clusters", "inspect clusters")

    # If json requested, preserve legacy machine output exactly.
    if format == "json":
        core_context: CoreContext = ctx.obj
        clusters = await logic.find_clusters_logic(core_context, n_clusters)
        typer.echo(json.dumps(clusters, default=str, indent=2))
        return

    # Otherwise, forward to canonical inspect command (rich output).
    try:
        from body.cli.commands.inspect import clusters_cmd
    except Exception as exc:  # pragma: no cover
        logger.debug(
            "diagnostics find-clusters: cannot import inspect.clusters_cmd: %s", exc
        )
        # Fallback to legacy rich output.
        core_context: CoreContext = ctx.obj
        clusters = await logic.find_clusters_logic(core_context, n_clusters)

        if not clusters:
            console.print("[yellow]No clusters found.[/yellow]")
            return

        console.print(f"[green]Found {len(clusters)} clusters:[/green]")
        for cluster in clusters:
            console.print(
                f"- {cluster.get('topic', 'Unknown')}: {cluster.get('size', 0)} items"
            )
        return

    await clusters_cmd(ctx, n_clusters=n_clusters)


@app.command("command-tree")
@core_command(dangerous=False, requires_context=False)
# ID: dd914ffc-2b27-43e5-a6a6-20695cb7e778
def cli_tree_command(
    ctx: typer.Context,
    format: str = typer.Option(
        "tree", "--format", help="Output format (tree|json|yaml)"
    ),
) -> None:
    """
    DEPRECATED alias for `inspect command-tree`.

    Notes:
    - `inspect command-tree` is canonical in the golden tree.
    - `inspect command-tree` currently does not support --format.
      Therefore json/yaml output remains implemented here until inspect is extended.
    """
    _deprecated("diagnostics command-tree", "inspect command-tree")

    # Import main app here to avoid circular imports at module level
    from body.cli.admin_cli import app as main_app

    logger.info("Building CLI Command Tree...")
    tree_data = logic.build_cli_tree_data(main_app)

    # Preserve legacy machine-readable outputs
    if format == "json":
        typer.echo(json.dumps(tree_data, indent=2))
        return

    if format == "yaml":
        typer.echo(yaml.dump(tree_data, sort_keys=False))
        return

    # Default 'tree': forward to canonical inspect command for golden-path UX.
    try:
        from body.cli.commands.inspect import command_tree_cmd
    except Exception as exc:  # pragma: no cover
        logger.debug(
            "diagnostics command-tree: cannot import inspect.command_tree_cmd: %s", exc
        )
        # Fallback to legacy rich rendering
        root = Tree("[bold blue]CORE CLI[/bold blue]")

        # ID: ac768415-a418-444b-b9b8-bf8556296c60
        def add_nodes(nodes: list[dict[str, Any]], parent: Tree) -> None:
            for node in nodes:
                label = f"[bold]{node['name']}[/bold]"
                if node.get("help"):
                    label += f": [dim]{node['help']}[/dim]"
                branch = parent.add(label)
                if "children" in node:
                    add_nodes(node["children"], branch)

        add_nodes(tree_data, root)
        console.print(root)
        return

    command_tree_cmd(ctx)


@app.command("debug-meta")
@core_command(dangerous=False, requires_context=False)
# ID: 59eb1e73-3e51-470c-8f1c-1c7c2142013d
def debug_meta_command(
    ctx: typer.Context,
    format: str = typer.Option("list", "--format", help="Output format (list|json)"),
) -> None:
    """Prints auditor's view of constitutional files."""
    paths = logic.get_meta_paths_logic()

    if format == "json":
        typer.echo(json.dumps(paths, indent=2))
        return

    for p in paths:
        console.print(p)


@app.command("unassigned-symbols")
@core_command(dangerous=False)
# ID: b39297a7-26db-47a6-a2d0-f2780cca9bb1
async def unassigned_symbols_command(
    ctx: typer.Context,
    format: str = typer.Option("table", "--format", help="Output format (table|json)"),
) -> None:
    """Finds symbols without # ID tags."""
    core_context: CoreContext = ctx.obj
    unassigned = await logic.get_unassigned_symbols_logic(core_context)

    if format == "json":
        typer.echo(json.dumps(unassigned, indent=2))
        return

    if not unassigned:
        console.print(
            "[green]Success! All governable symbols have assigned IDs.[/green]"
        )
        return

    console.print(
        f"[yellow]Found {len(unassigned)} symbols with no assigned ID:[/yellow]"
    )
    for item in unassigned:
        console.print(f"- {item.get('name')} ({item.get('file')})")


# Re-register existing commands from logic modules (legacy behavior maintained)
app.command("policy-coverage", help="Audits constitution coverage.")(policy_coverage)
app.command("manifest-hygiene", help="Checks capability manifests.")(manifest_hygiene)
app.command("cli-registry", help="Validates CLI registry schema.")(cli_registry)
app.command("legacy-tags", help="Scans for obsolete tags.")(check_legacy_tags)
