# src/body/cli/commands/inspect/diagnostics.py
# ID: 01a8bde7-f057-47f4-96f7-a99f3085c47d

"""
System diagnostics commands.

Commands:
- inspect command-tree - CLI hierarchy visualization
- inspect test-targets - Test complexity analysis
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from body.self_healing.test_target_analyzer import TestTargetAnalyzer
from cli.logic import diagnostics as diagnostics_logic
from shared.cli_utils import core_command
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


logger = getLogger(__name__)
console = Console()


@command_meta(
    canonical_name="inspect.command-tree",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Displays a hierarchical tree view of all available CLI commands",
)
@core_command(dangerous=False, requires_context=False)
# ID: 785bde18-d06d-4616-a451-28d107d9d059
def command_tree_cmd(ctx: typer.Context) -> None:
    """
    Displays a hierarchical tree view of all available CLI commands.

    Examples:
        core-admin inspect command-tree
    """
    from cli.admin_cli import app as main_app

    logger.info("Building CLI Command Tree...")
    tree_data = diagnostics_logic.build_cli_tree_data(main_app)

    root = Tree("[bold blue]CORE CLI[/bold blue]")

    # ID: 1ba3f389-d768-401f-98ea-62c1b844ff10
    def add_nodes(nodes: list[dict[str, Any]], parent: Tree) -> None:
        """Recursively add nodes to tree."""
        for node in nodes:
            label = f"[bold]{node['name']}[/bold]"
            if node.get("help"):
                label += f": [dim]{node['help']}[/dim]"

            branch = parent.add(label)
            if "children" in node:
                add_nodes(node["children"], branch)

    add_nodes(tree_data, root)
    console.print(root)


@command_meta(
    canonical_name="inspect.test-targets",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    summary="Identifies and classifies functions as SIMPLE or COMPLEX test targets",
)
@core_command(dangerous=False, requires_context=False)
# ID: 3a48c44a-7cfe-4383-a3b5-f7b2a1c3051a
def inspect_test_targets(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="The path to the Python file to analyze.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    """
    Identifies and classifies functions in a file as SIMPLE or COMPLEX test targets.

    SIMPLE targets:
    - Pure functions with no side effects
    - Clear input/output relationships
    - Low cyclomatic complexity

    COMPLEX targets:
    - Database interactions
    - External API calls
    - High cyclomatic complexity
    - Multiple dependencies

    Examples:
        core-admin inspect test-targets src/shared/utils/parsing.py
    """
    analyzer = TestTargetAnalyzer()
    targets = analyzer.analyze_file(file_path)

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
        style = "green" if target.classification == "SIMPLE" else "red"
        table.add_row(
            target.name,
            str(target.complexity),
            f"[{style}]{target.classification}[/{style}]",
            target.reason,
        )

    console.print(table)


# Export commands for registration
diagnostics_commands = [
    {"name": "command-tree", "func": command_tree_cmd},
    {"name": "test-targets", "func": inspect_test_targets},
]
