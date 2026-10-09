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

from cli.renderers.audit_overview import render_overview as _render_overview_groups
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity, EvidenceClass
from shared.models.audit_rendering import SeverityGroup
from shared.utils.audit_grouping import SEVERITY_ORDER, get_max_severity, group_findings


_SEVERITY_MAP = {str(s): s for s in AuditSeverity}
_EVIDENCE_MAP = {str(e): e for e in EvidenceClass}


# ID: ae8e7546-39a6-4b9b-a7ab-7f41162116f1
def to_audit_finding(raw: dict) -> AuditFinding:
    """Build an AuditFinding from a raw finding dict.

    Lives here (and not in src/cli/resources/code/audit.py) so the
    ADR-054 D4 CLI files can keep their imports inside `api.*` and
    `cli.*` — the shared.models dependency is centralised in this
    renderer module which already needs it for its own typing.
    """
    severity = _SEVERITY_MAP.get(
        str(raw.get("severity", "info")).lower(), AuditSeverity.INFO
    )
    # ADR-113: carry the engine's evidence class through; a missing or
    # unknown value stays ATTESTED (fail-closed), never a false PROVEN.
    evidence_class = _EVIDENCE_MAP.get(
        str(raw.get("evidence_class", "")).lower(), EvidenceClass.ATTESTED
    )
    return AuditFinding(
        check_id=raw.get("check_id") or raw.get("rule_id") or "unknown",
        severity=severity,
        message=raw.get("message", ""),
        file_path=raw.get("file_path"),
        line_number=raw.get("line_number"),
        context=raw.get("context", {}),
        evidence_class=evidence_class,
    )


logger = getLogger(__name__)
console = Console()


@dataclass
# ID: a010d8e0-b1db-4b16-acfe-733c996c7248
class AuditStats:
    """Execution statistics for a constitutional audit run.

    ``None`` means the run did not measure that figure (the offline path has
    no mapping-coverage or dispatch breakdown); it renders as "n/a", never
    as a false 0.
    """

    total_rules: int = 0
    executed_rules: int = 0
    coverage_percent: float | None = 0
    total_declared_rules: int = 0
    crashed_rules: int | None = 0
    unmapped_rules: int | None = 0
    effective_coverage_percent: float | None = 0
    # ADR-076 D4: effective per-rule dispatch mode counts
    context_level_rules: int | None = 0
    per_file_rules: int | None = 0


def _stat(value: float | None, fmt: str = "{}") -> str:
    """Format a stat value; an unmeasured one (None) reads "n/a"."""
    return "n/a" if value is None else fmt.format(value)


# ID: 0b88103e-949f-4a1d-9daf-c2042c6346b9
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
        f"Coverage: [cyan]{_stat(stats.coverage_percent, '{:.1f}%')}[/cyan]",
    )
    stats_table.add_row(
        f"Effective coverage: [cyan]{_stat(stats.effective_coverage_percent, '{:.1f}%')}[/cyan]",
        f"Crashed: [red]{_stat(stats.crashed_rules)}[/red]",
        f"Unmapped: [yellow]{_stat(stats.unmapped_rules)}[/yellow]",
    )
    stats_table.add_row(
        f"Duration: [dim]{duration:.2f}s[/dim]",
        f"Total findings: [cyan]{len(findings)}[/cyan]",
        f"Dispatch: [cyan]{_stat(stats.context_level_rules)}[/cyan] context-level · "
        f"[cyan]{_stat(stats.per_file_rules)}[/cyan] per-file",
    )
    console.print(
        Panel(stats_table, title="[bold]Audit Execution Stats[/bold]", expand=False)
    )
    console.print()
    groups: list[SeverityGroup] = group_findings(findings)
    _render_overview_groups(console, groups)
    console.print()
    _render_verdict(console, groups, verdict_str=verdict_str, passed=passed)


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
    # DEGRADED is a tri-state distinct from PASS/FAIL: the instrument
    # couldn't check some rules, so compliance is UNKNOWN. Render it in
    # yellow to signal "instrument compromised" rather than collapsing
    # into either green (pass) or red (fail).
    if label.upper() == "DEGRADED":
        style = "bold yellow"
        panel_style = "yellow"
    elif is_passed:
        style = "bold green"
        panel_style = "green"
    else:
        style = "bold red"
        panel_style = "red"
    console.print(
        Panel(
            Text(label, style=style),
            title="[bold white]Final Verdict[/bold white]",
            style=panel_style,
            expand=False,
        )
    )
