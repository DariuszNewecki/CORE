# src/cli/renderers/audit_overview.py
"""Renderer for audit overview table."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from shared.logger import getLogger
from shared.models.audit_rendering import SeverityGroup, get_severity_style


logger = getLogger(__name__)


# ID: a42afd0d-567d-4404-a401-aa26b2664246
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
    _render_iceberg_rollup(console, groups)


def _render_iceberg_rollup(console: Console, groups: list[SeverityGroup]) -> None:
    """Surface aggregate-quality-gate scale (ADR-098 D3).

    Per-file emission (ADR-098 D1) already makes the row count honest. This
    rollup adds the second half: how many underlying issues those rows
    represent. A rule that emits 290 findings carrying 779 underlying mypy
    errors renders as "quality.type_safety — 290 findings, 779 underlying
    issues", so a reader can size the iceberg from the overview alone.

    Opt-in via ``context.issue_count``: findings without it (every
    non-quality-gate finding) are ignored and the rollup is skipped entirely
    when no aggregate-gate findings are present.
    """
    rollup: dict[str, list[int]] = {}
    for group in groups:
        for finding in group.findings:
            issue_count = finding.context.get("issue_count")
            if not isinstance(issue_count, int) or issue_count < 1:
                continue
            entry = rollup.setdefault(finding.check_id, [0, 0])
            entry[0] += 1
            entry[1] += issue_count

    # Only worth showing when at least one rule's underlying issues exceed
    # its finding count — i.e. there is an actual iceberg to reveal.
    if not any(issues > findings for findings, issues in rollup.values()):
        return

    table = Table(
        title="[bold magenta]Aggregate Quality Gates[/bold magenta]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Rule", style="dim")
    table.add_column("Findings", justify="right", style="cyan")
    table.add_column("Underlying issues", justify="right", style="yellow")
    for check_id in sorted(rollup):
        findings, issues = rollup[check_id]
        table.add_row(check_id, str(findings), str(issues))
    console.print(table)
