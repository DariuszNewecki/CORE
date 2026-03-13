# src/cli/renderers/audit_overview.py
"""Renderer for audit overview table."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from shared.models.audit_rendering import SeverityGroup, get_severity_style


# ID: 6896cd69-d8a4-4177-8f8e-7738b811f687
def render_overview(console: Console, groups: list[SeverityGroup]) -> None:
    """Render overview table with severity counts and percentages."""
    total = sum(len(g.findings) for g in groups)
    if total == 0:
        console.print("[bold green]No findings.[/]")
        return
    table = Table(
        title="[bold magenta]Audit Overview[/bold magenta]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Severity", style="dim")
    table.add_column("Count", justify="right", style="cyan")
    table.add_column("%", justify="right", style="magenta")
    for group in groups:
        count = len(group.findings)
        if count == 0:
            continue
        pct = count / total * 100
        sev_text = Text(group.severity.name, style=get_severity_style(group.severity))
        table.add_row(sev_text, str(count), f"{pct:.1f}%")
    console.print(table)
