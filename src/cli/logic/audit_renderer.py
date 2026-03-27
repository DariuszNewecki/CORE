# src/cli/logic/audit_renderer.py
"""Facade/orchestrator for audit report rendering.

Orchestrates grouping and delegated rendering; preserves original behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.renderers.audit_detail import render_details as _render_details_groups
from cli.renderers.audit_overview import render_overview as _render_overview_groups
from shared.logger import getLogger
from shared.models import AuditFinding
from shared.models.audit_rendering import SeverityGroup
from shared.utils.audit_grouping import SEVERITY_ORDER, get_max_severity, group_findings


logger = getLogger(__name__)


@dataclass
# ID: b6f850ed-7599-49b1-8fd6-423ea130fa30
class AuditStats:
    """Execution statistics for a constitutional audit run."""

    total_rules: int = 0
    executed_rules: int = 0
    coverage_percent: float = 0
    total_declared_rules: int = 0
    crashed_rules: int = 0
    unmapped_rules: int = 0
    effective_coverage_percent: float = 0


# ID: 88bbf06d-5b83-4723-b2fb-19fe628b3dc2
def render_overview(
    console: Console,
    findings: list[AuditFinding],
    stats: AuditStats,
    duration: float,
    passed: bool,
    verdict_str: str | None = None,
) -> None:
    """Render audit stats panel + severity overview table."""
    stats_table = Table.grid(expand=True, padding=(0, 2))
    stats_table.add_row(
        f"Rules declared: [cyan]{stats.total_declared_rules}[/cyan]",
        f"Rules executed: [cyan]{stats.executed_rules}[/cyan]",
        f"Coverage: [cyan]{stats.coverage_percent:.1f}%[/cyan]",
    )
    stats_table.add_row(
        f"Effective coverage: [cyan]{stats.effective_coverage_percent:.1f}%[/cyan]",
        f"Crashed: [red]{stats.crashed_rules}[/red]",
        f"Unmapped: [yellow]{stats.unmapped_rules}[/yellow]",
    )
    stats_table.add_row(
        f"Duration: [dim]{duration:.2f}s[/dim]",
        f"Total findings: [cyan]{len(findings)}[/cyan]",
        "",
    )
    console.print(
        Panel(stats_table, title="[bold]Audit Execution Stats[/bold]", expand=False)
    )
    console.print()
    groups: list[SeverityGroup] = group_findings(findings)
    _render_overview_groups(console, groups)
    console.print()
    _render_verdict(console, groups, verdict_str=verdict_str, passed=passed)


# ID: 15fba057-c29d-4bc9-9ed1-feb9850255da
def render_detail(console: Console, findings: list[AuditFinding]) -> None:
    """Render detailed findings tables grouped by severity."""
    groups: list[SeverityGroup] = group_findings(findings)
    _render_details_groups(console, groups)


# ID: b71905e8-454b-4597-9282-9e09ae1dab4d
def render_audit_report(
    findings: list[AuditFinding], console: Console | None = None
) -> None:
    """Main entrypoint: render full audit report (overview, details, verdict)."""
    if console is None:
        console = Console()
    groups: list[SeverityGroup] = group_findings(findings)
    _render_overview_groups(console, groups)
    console.print()
    _render_details_groups(console, groups)
    console.print()
    _render_verdict(console, groups)


def _render_verdict(
    console: Console,
    groups: list[SeverityGroup],
    verdict_str: str | None = None,
    passed: bool | None = None,
) -> None:
    """Render final verdict panel."""
    max_sev = get_max_severity(groups)
    if passed is not None:
        is_passed = passed
    else:
        is_passed = max_sev is None or SEVERITY_ORDER.get(max_sev, 0) < 3
    if verdict_str:
        label = verdict_str
    else:
        label = "PASSED" if is_passed else "FAILED"
    style = "bold green" if is_passed else "bold red"
    panel_style = "green" if is_passed else "red"
    console.print(
        Panel(
            Text(label, style=style),
            title="[bold white]Final Verdict[/bold white]",
            style=panel_style,
            expand=False,
        )
    )
