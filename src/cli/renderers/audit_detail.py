# src/cli/renderers/audit_detail.py
from shared.logger import getLogger


logger = getLogger(__name__)
"""Renderer for detailed audit findings."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shared.models.audit_rendering import SeverityGroup, get_severity_style


# ID: 5d19aa95-ce9e-49b4-b7eb-7f32c9bfd431
def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    return text[:max_len] + "..." if len(text) > max_len else text


# ID: eb606556-5524-43c9-82b2-9706ba6c4930
def render_details(console: Console, groups: list[SeverityGroup]) -> None:
    """Render detailed tables for each severity group in panels."""
    for group in groups:
        count = len(group.findings)
        if count == 0:
            continue
        inner_table = Table(show_header=True, header_style="bold white")
        inner_table.add_column("ID", style="cyan", width=12, no_wrap=True)
        inner_table.add_column("Title", style="bold white")
        inner_table.add_column("Description", min_width=40)
        inner_table.add_column("Recommendation", min_width=30)
        for finding in group.findings:
            desc = truncate(finding.description, 80)
            rec = truncate(str(getattr(finding, "recommendation", "N/A")), 60)
            inner_table.add_row(finding.id, finding.title, desc, rec)
        title = f"{group.severity.name} ({count} findings)"
        style = get_severity_style(group.severity)
        panel = Panel(inner_table, title=title, border_style=style, expand=False)
        logger.info(panel)
        logger.info()
