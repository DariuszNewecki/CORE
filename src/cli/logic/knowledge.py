# src/cli/logic/knowledge.py
"""
Implements the logic for knowledge-related CLI commands, such as finding
common, duplicated helper functions across the codebase.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.table import Table

from features.self_healing.knowledge_consolidation_service import (
    find_structurally_similar_helpers,
)

console = Console()


# ID: a4b9c1d8-f3e2-4b1e-a9d5-f8c3d7f4b1e9
def find_common_knowledge(
    min_occurrences: int = 3,
    max_lines: int = 10,
):
    """
    CLI logic to find and display structurally similar helper functions.
    """
    console.print(
        "[bold cyan]🔍 Scanning for structurally similar helper functions...[/bold cyan]"
    )

    duplicates = asyncio.run(
        asyncio.to_thread(find_structurally_similar_helpers, min_occurrences, max_lines)
    )

    if not duplicates:
        console.print(
            "[bold green]✅ No common helper functions found meeting the criteria.[/bold green]"
        )
        return

    console.print(
        f"\n[bold yellow]Found {len(duplicates)} cluster(s) of duplicated helper functions:[/bold yellow]"
    )

    for i, (hash_val, locations) in enumerate(duplicates.items(), 1):
        table = Table(
            title=f"Cluster #{i} (Found {len(locations)} times)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("File Path", style="cyan")
        table.add_column("Line", style="magenta", justify="right")

        for file_path, line_num in sorted(locations):
            table.add_row(file_path, str(line_num))

        console.print(table)

    console.print(
        "\n[bold]Next Step:[/bold] Use these findings to refactor and consolidate helpers into `src/shared/utils/` to uphold the `dry_by_design` principle."
    )
