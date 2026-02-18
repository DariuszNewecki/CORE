# src/body/cli/logic/audit_renderer.py
# ID: 307b8ea7-8593-42cc-a259-0fbdc8580f9e

"""
Audit Renderer - Human-readable Rich output for constitutional audit results.

Provides two detail levels:
- Overview: Health card, severity breakdown, top offenders, suggested fixes
- Detail:   Overview + every finding grouped by rule with file:line locations

HARDENED (V2.5.0):
- Three-state verdict display: PASS / FAIL / DEGRADED
- Crashed and unmapped rule counts visible in health card
- Effective coverage uses true denominator (all declared rules)

ARCHITECTURAL NOTE:
This is a CLI-layer rendering module. It takes data and produces Rich output.
No business logic, no filesystem access, no database queries.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from shared.models import AuditFinding, AuditSeverity


# ============================================================================
# DATA STRUCTURES
# ============================================================================

SEVERITY_ENFORCEMENT = {
    AuditSeverity.ERROR: "BLOCKING",
    AuditSeverity.WARNING: "REPORTING",
    AuditSeverity.INFO: "ADVISORY",
}

SEVERITY_ICON = {
    AuditSeverity.ERROR: "\U0001f6ab",
    AuditSeverity.WARNING: "\u26a0\ufe0f",
    AuditSeverity.INFO: "\u2139\ufe0f",
}

SEVERITY_COLOR = {
    AuditSeverity.ERROR: "red",
    AuditSeverity.WARNING: "yellow",
    AuditSeverity.INFO: "dim",
}

# Known fix commands for common check_ids
FIX_HINTS: dict[str, str] = {
    "purity.stable_id_anchor": "core-admin symbols fix-ids --write",
    "purity.no_todo_placeholders": "core-admin code fix-placeholders --write",
    "linkage.duplicate_id_collision": "core-admin symbols fix-duplicate-ids --write",
    "architecture.max_file_size": "(manual) split large files per modularity rules",
    "purity.module_docstring": "core-admin code fix-docstrings --write",
    "purity.no_print_statements": "core-admin code fix-logging --write",
}


@dataclass
# ID: d7a3e1f2-8b4c-5d6e-a0f1-c2d3e4f5a6b7
class AuditStats:
    """Execution statistics from the constitutional audit.

    HARDENED (V2.5.0): Now includes true denominator, crashed, and unmapped counts.
    """

    total_rules: int = 0
    executed_rules: int = 0
    coverage_percent: int = 0
    # P0 additions
    total_declared_rules: int = 0
    crashed_rules: int = 0
    unmapped_rules: int = 0
    effective_coverage_percent: int = 0


@dataclass
# ID: e8b4f2a3-9c5d-6e7f-b1a2-d3e4f5a6b7c8
class RuleGroup:
    """Findings grouped by check_id for display."""

    check_id: str
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    # ID: 7a57be7f-40a2-4ed7-b180-231e01e2b820
    def count(self) -> int:
        return len(self.findings)

    @property
    # ID: 2bb54701-726f-46d5-b837-0cf6377f2ba8
    def max_severity(self) -> AuditSeverity:
        if not self.findings:
            return AuditSeverity.INFO
        return max(f.severity for f in self.findings)


# ============================================================================
# GROUPING HELPERS
# ============================================================================


# ID: f9c5a3b4-0d6e-7f8a-c2b3-e4f5a6b7c8d9
def _group_by_rule(findings: list[AuditFinding]) -> list[RuleGroup]:
    """Group findings by check_id, sorted by severity (highest first) then count."""
    groups: dict[str, RuleGroup] = {}
    for f in findings:
        if f.check_id not in groups:
            groups[f.check_id] = RuleGroup(check_id=f.check_id)
        groups[f.check_id].findings.append(f)

    return sorted(
        groups.values(),
        key=lambda g: (-g.max_severity.value, -g.count),
    )


# ID: a0d6b4c5-1e7f-8a9b-d3c4-f5a6b7c8d9e0
def _group_by_severity(
    findings: list[AuditFinding],
) -> dict[AuditSeverity, list[AuditFinding]]:
    """Partition findings by severity level."""
    result: dict[AuditSeverity, list[AuditFinding]] = {
        AuditSeverity.ERROR: [],
        AuditSeverity.WARNING: [],
        AuditSeverity.INFO: [],
    }
    for f in findings:
        result[f.severity].append(f)
    return result


# ID: b1e7c5d6-2f8a-9b0c-e4d5-a6b7c8d9e0f1
def _collect_fix_hints(findings: list[AuditFinding]) -> list[str]:
    """Deduplicated fix hints for the findings present."""
    seen: set[str] = set()
    hints: list[str] = []
    check_ids = {f.check_id for f in findings}

    for check_id, hint in FIX_HINTS.items():
        if check_id in check_ids and hint not in seen:
            seen.add(hint)
            hints.append(hint)

    return hints


# ============================================================================
# OVERVIEW RENDERING
# ============================================================================


# ID: c2f8d6e7-3a9b-0c1d-f5e6-b7c8d9e0f1a2
def render_overview(
    console: Console,
    findings: list[AuditFinding],
    stats: AuditStats,
    duration_sec: float,
    passed: bool,
    verdict_str: str | None = None,
) -> None:
    """
    Render the audit overview health card.

    Shows: execution stats, severity breakdown, rule-level summary table,
    and suggested fix commands.

    HARDENED: Now accepts optional verdict_str for three-state display.
    """
    by_severity = _group_by_severity(findings)
    rule_groups = _group_by_rule(findings)

    # — Verdict —
    if verdict_str is None:
        # Backward compat: derive from bool
        verdict_str = "PASS" if passed else "FAIL"

    if verdict_str == "DEGRADED":
        verdict_color = "yellow"
        verdict_text = "DEGRADED (enforcement failures — compliance status UNKNOWN)"
    elif verdict_str == "PASS":
        verdict_color = "green"
        verdict_text = "PASSED (no blocking violations)"
    else:
        verdict_color = "red"
        verdict_text = "FAILED (blocking violations detected)"

    # — Health Card —
    card_lines = [
        f"Rules Executed : {stats.executed_rules}/{stats.total_rules} ({stats.coverage_percent}%)",
    ]

    # P0 additions: show truthful coverage when available
    if stats.total_declared_rules > 0:
        card_lines.append(
            f"True Coverage  : {stats.executed_rules}/{stats.total_declared_rules} "
            f"({stats.effective_coverage_percent}%)"
        )

    if stats.crashed_rules > 0:
        card_lines.append(
            f"Crashed Rules  : [bold red]{stats.crashed_rules}[/bold red] "
            f"(enforcement failures — treat as non-compliant)"
        )

    if stats.unmapped_rules > 0:
        card_lines.append(
            f"Unmapped Rules : [yellow]{stats.unmapped_rules}[/yellow] "
            f"(declared but not enforceable)"
        )

    card_lines.extend(
        [
            f"Total Findings : {len(findings)}",
            f"Duration       : {duration_sec:.1f}s",
            f"Verdict        : [{verdict_color}]{verdict_text}[/{verdict_color}]",
        ]
    )

    console.print()
    console.print(
        Panel(
            "\n".join(card_lines),
            title="[bold]Constitutional Audit[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # — Severity Breakdown —
    for severity in (AuditSeverity.ERROR, AuditSeverity.WARNING, AuditSeverity.INFO):
        count = len(by_severity[severity])
        icon = SEVERITY_ICON[severity]
        label = SEVERITY_ENFORCEMENT[severity]
        color = SEVERITY_COLOR[severity]

        bar_filled = min(count, 30)
        bar = "\u2588" * bar_filled

        console.print(
            f"  {icon} [{color}]{label:<10}[/{color}] "
            f"[bold]{count:>4}[/bold]  [{color}]{bar}[/{color}]"
        )

    console.print()

    # — Rule Summary Table —
    if rule_groups:
        table = Table(
            show_header=True,
            header_style="bold",
            title="Findings by Rule",
            title_style="bold cyan",
            padding=(0, 1),
        )
        table.add_column("Rule", style="cyan", min_width=35)
        table.add_column("Level", min_width=10)
        table.add_column("ERR", justify="right", style="red")
        table.add_column("WARN", justify="right", style="yellow")
        table.add_column("INFO", justify="right", style="dim")
        table.add_column("Total", justify="right", style="bold")

        for group in rule_groups:
            sev_counts: Counter[AuditSeverity] = Counter()
            for f in group.findings:
                sev_counts[f.severity] += 1

            enforcement = SEVERITY_ENFORCEMENT[group.max_severity]
            enforcement_color = SEVERITY_COLOR[group.max_severity]

            table.add_row(
                group.check_id,
                Text(enforcement.lower(), style=enforcement_color),
                str(sev_counts.get(AuditSeverity.ERROR, 0) or ""),
                str(sev_counts.get(AuditSeverity.WARNING, 0) or ""),
                str(sev_counts.get(AuditSeverity.INFO, 0) or ""),
                str(group.count),
            )

        console.print(table)
        console.print()

    # — Fix Suggestions —
    hints = _collect_fix_hints(findings)
    if hints:
        console.print("[bold]\U0001f4a1 Suggested fixes:[/bold]")
        for hint in hints:
            console.print(f"   [cyan]{hint}[/cyan]")
        console.print()


# ============================================================================
# DETAIL RENDERING
# ============================================================================


# ID: d3a9e7f8-4b0c-1d2e-a6f7-c8d9e0f1a2b3
def render_detail(
    console: Console,
    findings: list[AuditFinding],
) -> None:
    """
    Render detailed findings grouped by severity, then by rule.

    Each finding shows file:line and message.
    """
    by_severity = _group_by_severity(findings)

    for severity in (AuditSeverity.ERROR, AuditSeverity.WARNING, AuditSeverity.INFO):
        level_findings = by_severity[severity]
        label = SEVERITY_ENFORCEMENT[severity]
        icon = SEVERITY_ICON[severity]
        color = SEVERITY_COLOR[severity]

        console.rule(f"[{color}]{icon} {label} ({len(level_findings)})[/{color}]")

        if not level_findings:
            console.print("  [dim](none)[/dim]")
            console.print()
            continue

        # Sub-group by check_id within this severity
        sub_groups: dict[str, list[AuditFinding]] = defaultdict(list)
        for f in level_findings:
            sub_groups[f.check_id].append(f)

        for check_id in sorted(sub_groups, key=lambda k: -len(sub_groups[k])):
            group_findings = sub_groups[check_id]
            count = len(group_findings)
            noun = "finding" if count == 1 else "findings"

            console.print(
                f"\n  [{color}][bold]{check_id}[/bold][/{color}] " f"({count} {noun})"
            )

            for f in group_findings:
                location = _format_location(f)
                console.print(f"  \u251c\u2500 {location}")
                console.print(f"  \u2502  [dim]{f.message}[/dim]")

        console.print()


# ID: e4b0f8a9-5c1d-2e3f-b7a8-d9e0f1a2b3c4
def _format_location(finding: AuditFinding) -> str:
    """Format file:line location string for a finding."""
    if not finding.file_path:
        return "[dim](no file)[/dim]"

    location = finding.file_path
    if finding.line_number:
        location = f"{location}:{finding.line_number}"

    return f"[bold]{location}[/bold]"
