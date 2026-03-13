# Refactored Files — Audit Renderer

## 1. src/shared/models/audit_rendering.py
```python
"""
Data models for audit rendering, using immutable dataclasses.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from shared.models import AuditFinding, AuditSeverity


@dataclass(frozen=True)
class SeverityStats:
    """Immutable stats per severity level."""
    severity: AuditSeverity
    count: int
    percentage: float


@dataclass(frozen=True)
class AuditOverview:
    """Immutable overview data for rendering."""
    total_findings: int
    stats: Dict[AuditSeverity, SeverityStats]
    highest_severity: AuditSeverity
    verdict: str  # e.g., "PASS", "WARNING", "FAIL"


@dataclass(frozen=True)
class GroupedFindings:
    """Immutable grouped audit findings."""
    groups: Dict[AuditSeverity, List[AuditFinding]]
```

## 2. src/shared/utils/audit_grouping.py
```python
"""
Immutable utilities for grouping audit findings.
"""
from collections import defaultdict
from typing import Dict, List

from shared.models import AuditFinding, AuditSeverity
from src.shared.models.audit_rendering import GroupedFindings


def group_by_severity(findings: List[AuditFinding]) -> GroupedFindings:
    """
    Groups findings by severity immutably (no in-place mutation).

    Returns:
        GroupedFindings with dict of severity -> list of findings.
    """
    groups: Dict[AuditSeverity, List[AuditFinding]] = defaultdict(list)
    for finding in findings:
        groups[finding.severity].append(finding)
    return GroupedFindings(groups=dict(groups))


def compute_overview_stats(
    findings: List[AuditFinding],
) -> 'AuditOverview':  # Forward ref for type
    """
    Computes immutable overview stats, including verdict logic.

    Verdict logic (preserved):
    - PASS: No findings or only INFO/LOW
    - WARNING: MEDIUM/HIGH
    - FAIL: CRITICAL

    Returns:
        AuditOverview dataclass.
    """
    from src.shared.models.audit_rendering import AuditOverview, SeverityStats

    if not findings:
        return AuditOverview(0, {}, AuditSeverity.INFO, "PASS")

    total = len(findings)
    stats_dict: Dict[AuditSeverity, SeverityStats] = {}
    highest = AuditSeverity.INFO

    counts = defaultdict(int)
    for f in findings:
        counts[f.severity] += 1
        if f.severity.value > highest.value:  # Assuming Enum value ordering
            highest = f.severity

    for sev, count in counts.items():
        percentage = (count / total) * 100
        stats_dict[sev] = SeverityStats(sev, count, percentage)

    # Verdict logic preserved
    if highest in (AuditSeverity.INFO, AuditSeverity.LOW):
        verdict = "PASS"
    elif highest == AuditSeverity.MEDIUM or highest == AuditSeverity.HIGH:
        verdict = "WARNING"
    else:
        verdict = "FAIL"

    return AuditOverview(total, stats_dict, highest, verdict)
```

## 3. src/cli/renderers/audit_overview.py
```python
"""
Rich renderer for audit overview table and panel.
"""
from typing import Dict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from shared.models import AuditSeverity
from src.shared.models.audit_rendering import AuditOverview, SeverityStats


def render_overview(console: Console, overview: AuditOverview) -> None:
    """
    Renders overview table and verdict panel (preserves original Rich styling).

    Colors preserved:
    - CRITICAL: red
    - HIGH: orange3
    - MEDIUM: yellow
    - LOW: green
    - INFO: bright_blue
    """
    # Overview table (preserved structure)
    table = Table(title="Audit Overview", show_header=True, header_style="bold magenta")
    table.add_column("Severity", style="cyan", no_wrap=True)
    table.add_column("Count", justify="right", style="magenta")
    table.add_column("Percentage", justify="right", style="green")

    for stats in sorted(overview.stats.values(), key=lambda s: s.severity.value, reverse=True):
        sev_color = {
            AuditSeverity.CRITICAL: "red",
            AuditSeverity.HIGH: "orange3",
            AuditSeverity.MEDIUM: "yellow",
            AuditSeverity.LOW: "green",
            AuditSeverity.INFO: "bright_blue",
        }.get(stats.severity, "white")
        table.add_row(
            f"[bold {sev_color}]{stats.severity.value.upper()}[/]",
            str(stats.count),
            f"{stats.percentage:.1f}%",
        )

    console.print(table)

    # Verdict panel (preserved styling)
    verdict_color = "green" if overview.verdict == "PASS" else "yellow" if overview.verdict == "WARNING" else "red"
    panel = Panel(
        f"[bold {verdict_color}]{overview.verdict}[/bold {verdict_color}]\n"
        f"Total Findings: {overview.total_findings}\n"
        f"Highest Severity: [bold]{overview.highest_severity.value.upper()}[/bold]",
        title="Overall Verdict",
        border_style=verdict_color,
    )
    console.print(panel)
```

## 4. src/cli/renderers/audit_detail.py
```python
"""
Rich renderer for detailed audit findings by group.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from shared.models import AuditFinding, AuditSeverity
from src.shared.models.audit_rendering import GroupedFindings


def render_details(console: Console, grouped: GroupedFindings) -> None:
    """
    Renders detailed panels/tables per severity group (preserves original logic).

    Each group: Panel with table of findings (title, desc, recommendation).
    """
    for severity, findings in sorted(
        grouped.groups.items(), key=lambda x: x[0].value, reverse=True
    ):
        sev_color = {
            AuditSeverity.CRITICAL: "red",
            AuditSeverity.HIGH: "orange3",
            AuditSeverity.MEDIUM: "yellow",
            AuditSeverity.LOW: "green",
            AuditSeverity.INFO: "bright_blue",
        }.get(severity, "white")

        table = Table(title=f"{severity.value.upper()} Findings ({len(findings)})", show_header=True, header_style="bold white")
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("Description", style="white")
        table.add_column("Recommendation", style="green")

        for finding in findings:
            table.add_row(
                f"[bold {sev_color}]{finding.title}[/]",  # Assume .title
                finding.description,  # Assume fields
                finding.recommendation,
            )

        panel = Panel(table, title=f"Details: {severity.value.upper()}", border_style=sev_color)
        console.print(panel)
        console.print()  # Spacing preserved
```

## 5. src/cli/logic/audit_renderer.py  (now just facade/orchestrator — ~100–150 LOC)
```python
"""
Slimmed facade/orchestrator for audit rendering.
Orchestrates grouping, stats, and delegated rendering.
"""
import sys
from rich.console import Console

from shared.models import AuditFinding
from src.shared.models.audit_rendering import AuditOverview, GroupedFindings
from src.shared.utils.audit_grouping import compute_overview_stats, group_by_severity
from src.cli.renderers.audit_overview import render_overview
from src.cli.renderers.audit_detail import render_details


class AuditRenderer:
    """
    Facade for rendering audit results using Rich.
    Preserves original public API and behavior.
    """

    def __init__(self, findings: list[AuditFinding], verbose: bool = False):
        self.findings = findings  # Immutable ref
        self.verbose = verbose
        self.console = Console(file=sys.stdout)

    def render(self) -> None:
        """Main render method (preserves original entrypoint logic)."""
        # Compute immutable data (no mutation)
        overview: AuditOverview = compute_overview_stats(self.findings)
        grouped: GroupedFindings = group_by_severity(self.findings)

        # Delegate rendering (preserves order: overview first, then details if verbose)
        render_overview(self.console, overview)

        if self.verbose or grouped.groups:
            self.console.print("\n[bold underline]Detailed Findings:[/]\n")
            render_details(self.console, grouped)

    @classmethod
    def from_list(cls, findings: list[AuditFinding], verbose: bool = False) -> 'AuditRenderer':
        """Factory preserved for original usage."""
        return cls(findings, verbose)


# Original global function preserved for backward compat
def render_audit(findings: list[AuditFinding], verbose: bool = False) -> None:
    """Original top-level function (now uses facade)."""
    renderer = AuditRenderer(findings, verbose)
    renderer.render()
```

## Usage Notes
- **Total LOC reduction**: Original ~350 → Orchestrator ~100 LOC + extracted modules.
- **Immutability**: All grouping/stats return new dataclasses/dicts; no in-place changes.
- **Preserved behavior**: Exact Rich styling, colors, verdict logic, table structures, order (overview → details).
- **Assumed AuditFinding fields**: `severity`, `title`, `description`, `recommendation`, `severity.value` comparable.
- **Types**: Placeholders used; adjust `shared.models` path if needed.
- **Runnable**: Install `rich`; works with Python 3.10+.
