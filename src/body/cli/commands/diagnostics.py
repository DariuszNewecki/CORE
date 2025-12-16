# src/body/cli/commands/diagnostics.py

"""
src/body/cli/commands/diagnostics.py

Diagnostic Command Group.
Compliance:
- command_patterns.yaml: Inspect Pattern (output to stdout, --format support).
- logging_standards.yaml: Use print()/rich only in CLI entry points.
"""

from __future__ import annotations

import asyncio
import json

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
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
# Help text defines this group's purpose
app = typer.Typer(help="Deep diagnostic and integrity checks.")
console = Console()


@app.command("find-clusters")
# ID: 91856850-423f-4c27-90c3-e06f56a3841a
def find_clusters_command(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="Number of clusters."
    ),
    format: str = typer.Option("table", "--format", help="Output format (table|json)"),
):
    """Finds semantic capability clusters."""
    core_context: CoreContext = ctx.obj
    clusters = asyncio.run(logic.find_clusters_logic(core_context, n_clusters))

    if format == "json":
        print(json.dumps(clusters, default=str, indent=2))
    else:
        # Default human-readable output
        if not clusters:
            console.print("[yellow]No clusters found.[/yellow]")
            return

        console.print(f"[green]Found {len(clusters)} clusters:[/green]")
        for cluster in clusters:
            console.print(
                f"- {cluster.get('topic', 'Unknown')}: {cluster.get('size', 0)} items"
            )


@app.command("command-tree")
# ID: dd914ffc-2b27-43e5-a6a6-20695cb7e778
def cli_tree_command(
    format: str = typer.Option(
        "tree", "--format", help="Output format (tree|json|yaml)"
    ),
):
    """Displays hierarchical tree view of CLI commands."""
    # Import main app here to avoid circular imports at module level
    from body.cli.admin_cli import app as main_app

    logger.info("Building CLI Command Tree...")
    tree_data = logic.build_cli_tree_data(main_app)

    # 1. JSON Output
    if format == "json":
        print(json.dumps(tree_data, indent=2))
        return

    # 2. YAML Output
    if format == "yaml":
        print(yaml.dump(tree_data, sort_keys=False))
        return

    # 3. Rich Tree Output (Default)
    root = Tree("[bold blue]CORE CLI[/bold blue]")

    # ID: f97c89b7-8b61-4682-945f-ef439efbd1c0
    def add_nodes(nodes, parent):
        for node in nodes:
            label = f"[bold]{node['name']}[/bold]"
            if node.get("help"):
                label += f": [dim]{node['help']}[/dim]"

            branch = parent.add(label)
            if "children" in node:
                add_nodes(node["children"], branch)

    add_nodes(tree_data, root)
    console.print(root)


@app.command("debug-meta")
# ID: 59eb1e73-3e51-470c-8f1c-1c7c2142013d
def debug_meta_command(
    format: str = typer.Option("list", "--format", help="Output format (list|json)"),
):
    """Prints auditor's view of constitutional files."""
    paths = logic.get_meta_paths_logic()

    if format == "json":
        print(json.dumps(paths, indent=2))
    else:
        for p in paths:
            console.print(p)


@app.command("unassigned-symbols")
# ID: b39297a7-26db-47a6-a2d0-f2780cca9bb1
def unassigned_symbols_command(
    format: str = typer.Option("table", "--format", help="Output format (table|json)"),
):
    """Finds symbols without # ID tags."""
    unassigned = logic.get_unassigned_symbols_logic()

    if format == "json":
        print(json.dumps(unassigned, indent=2))
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
