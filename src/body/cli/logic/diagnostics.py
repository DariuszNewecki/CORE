# src/body/cli/logic/diagnostics.py

"""
Aggregates deep diagnostic checks from specialized modules.
Acts as the wiring center for the 'diagnostics' command group.
"""

from __future__ import annotations

import asyncio

import typer
from features.introspection.audit_unassigned_capabilities import get_unassigned_symbols
from features.introspection.graph_analysis_service import find_semantic_clusters
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from shared.config import settings
from shared.context import CoreContext
from shared.utils.constitutional_parser import get_all_constitutional_paths

# Import extracted logic
from .diagnostics_policy import policy_coverage
from .diagnostics_registry import check_legacy_tags, cli_registry, manifest_hygiene

console = Console()
diagnostics_app = typer.Typer(help="Deep diagnostic and integrity checks.")


async def _async_find_clusters(context: CoreContext, n_clusters: int):
    """Async helper that contains the core logic for the command."""
    console.print(
        f"🚀 Finding semantic clusters with [bold cyan]n_clusters={n_clusters}[/bold cyan]..."
    )

    if context.qdrant_service is None and context.registry:
        try:
            context.qdrant_service = await context.registry.get_qdrant_service()
        except Exception as e:
            console.print(
                f"[bold red]❌ Failed to initialize QdrantService: {e}[/bold red]"
            )
            return

    clusters = await find_semantic_clusters(
        qdrant_service=context.qdrant_service, n_clusters=n_clusters
    )

    if not clusters:
        console.print("⚠️  No clusters found.")
        return

    console.print(f"✅ Found {len(clusters)} clusters. Displaying all, sorted by size.")

    for i, cluster in enumerate(clusters):
        if not cluster:
            continue

        table = Table(
            title=f"Semantic Cluster #{i + 1} ({len(cluster)} symbols)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Symbol Key", style="cyan", no_wrap=True)

        for symbol_key in sorted(cluster):
            table.add_row(symbol_key)

        console.print(table)


@diagnostics_app.command(
    "find-clusters",
    help="Finds and displays all semantic capability clusters, sorted by size.",
)
# ID: fb7f9a46-4053-4a2b-bbcb-b937ffa55909
def find_clusters_command_sync(
    ctx: typer.Context,
    n_clusters: int = typer.Option(
        25, "--n-clusters", "-n", help="The number of clusters to find."
    ),
):
    """Synchronous Typer wrapper for the async clustering logic."""
    core_context: CoreContext = ctx.obj
    asyncio.run(_async_find_clusters(core_context, n_clusters))


def _add_cli_nodes(tree_node: Tree, cli_app: typer.Typer):
    for cmd_info in sorted(cli_app.registered_commands, key=lambda c: c.name or ""):
        if not cmd_info.name:
            continue
        help_text = cmd_info.help.split("\n")[0] if cmd_info.help else ""
        tree_node.add(
            f"[bold yellow]⚡ {cmd_info.name}[/bold yellow] [dim]- {help_text}[/dim]"
        )
    for group_info in sorted(cli_app.registered_groups, key=lambda g: g.name or ""):
        if not group_info.name:
            continue
        help_text = (
            group_info.typer_instance.info.help.split("\n")[0]
            if group_info.typer_instance.info.help
            else ""
        )
        branch = tree_node.add(
            f"[cyan]📂 {group_info.name}[/cyan] [dim]- {help_text}[/dim]"
        )
        _add_cli_nodes(branch, group_info.typer_instance)


@diagnostics_app.command(
    "cli-tree", help="Displays a hierarchical tree view of all available CLI commands."
)
# ID: 30a6dcde-a174-48de-8f0f-327cbafec340
def cli_tree():
    """Builds and displays the CLI command tree."""
    from body.cli.admin_cli import app as main_app

    console.print("[bold cyan]🚀 Building CLI Command Tree...[/bold cyan]")
    tree = Tree(
        "[bold magenta]🏛️ CORE Admin CLI Commands[/bold magenta]",
        guide_style="bold bright_blue",
    )
    _add_cli_nodes(tree, main_app)
    console.print(tree)


@diagnostics_app.command(
    "debug-meta", help="Prints the auditor's view of all required constitutional files."
)
# ID: 993e903f-d239-44bf-95ec-1eb0422094cd
def debug_meta_paths():
    """A diagnostic tool that prints all file paths indexed in meta.yaml."""
    console.print(
        "[bold yellow]--- Auditor's Interpretation of meta.yaml ---[/bold yellow]"
    )
    required_paths = get_all_constitutional_paths(settings._meta_config, settings.MIND)
    for path in sorted(list(required_paths)):
        console.print(path)


@diagnostics_app.command(
    "unassigned-symbols", help="Finds symbols without a universal # ID tag."
)
# ID: 6e1b1104-fd07-4865-88bd-d376da96c0f4
def unassigned_symbols():
    unassigned = get_unassigned_symbols()
    if not unassigned:
        console.print(
            "[bold green]✅ Success! All governable symbols have an assigned ID tag.[/bold green]"
        )
        return
    console.print(
        f"\n[bold red]❌ Found {len(unassigned)} symbols with no assigned ID:[/bold red]"
    )
    table = Table(title="Untagged Symbols ('Orphaned Logic')")
    table.add_column("Symbol Key", style="cyan", no_wrap=True)
    table.add_column("File", style="yellow")
    table.add_column("Line", style="magenta")
    for symbol in sorted(unassigned, key=lambda s: s["key"]):
        table.add_row(symbol["key"], symbol["file"], str(symbol["line_number"]))
    console.print(table)
    console.print("\n[bold]Action Required:[/bold] Run 'knowledge sync' to assign IDs.")


# Register commands extracted to other modules
diagnostics_app.command(
    "policy-coverage", help="Audits the constitution for policy coverage and integrity."
)(policy_coverage)

diagnostics_app.command(
    "manifest-hygiene",
    help="Checks for capabilities declared in the wrong domain manifest file.",
)(manifest_hygiene)

diagnostics_app.command(
    "cli-registry", help="Validates the CLI registry against its constitutional schema."
)(cli_registry)

diagnostics_app.command("legacy-tags", help="Scans the codebase for obsolete tags.")(
    check_legacy_tags
)
