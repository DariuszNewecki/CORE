# src/cli/renderers/audit_detail.py
"""Renderer for detailed audit findings (ADR-098 D3)."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from shared.models.audit_rendering import SeverityGroup, get_severity_style


# ID: 5d19aa95-ce9e-49b4-b7eb-7f32c9bfd431
def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    return text[:max_len] + "..." if len(text) > max_len else text


def _file_cell(finding: object) -> str:
    """Build the File cell, appending (xN) for quality-gate findings (ADR-098 D3).

    When a finding carries context.issue_count > 1, the underlying issue count
    exceeds the finding count. Append the multiplier so a reader can size the
    iceberg from the detail row without opening the tool output.
    """
    file_path: str = str(getattr(finding, "file_path", "") or "")
    issue_count = (getattr(finding, "context", None) or {}).get("issue_count")
    if isinstance(issue_count, int) and issue_count > 1 and file_path:
        return f"{file_path} (x{issue_count})"
    return file_path or "-"


# ID: eb606556-5524-43c9-82b2-9706ba6c4930
def render_details(console: Console, groups: list[SeverityGroup]) -> None:
    """Render detailed tables for each severity group in panels (ADR-098 D3)."""
    for group in groups:
        count = len(group.findings)
        if count == 0:
            continue
        inner_table = Table(show_header=True, header_style="bold white")
        inner_table.add_column("Check ID", style="cyan", width=30, no_wrap=True)
        inner_table.add_column("File", style="yellow")
        inner_table.add_column("Message", min_width=40, overflow="fold")
        for finding in group.findings:
            inner_table.add_row(
                escape(getattr(finding, "check_id", "-") or "-"),
                escape(_file_cell(finding)),
                escape(truncate(getattr(finding, "message", ""), 80)),
            )
        title = f"{group.severity.name} ({count} findings)"
        style = get_severity_style(group.severity)
        panel = Panel(inner_table, title=title, border_style=style, expand=False)
        console.print(panel)
        console.print()
