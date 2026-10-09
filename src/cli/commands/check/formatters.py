# src/cli/commands/check/formatters.py
"""
Output formatters for audit results.

Handles Rich UI presentation of findings, summaries, and statistics.
All formatting logic lives here - keeps command code clean.
"""

from __future__ import annotations

import re
from collections import defaultdict

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity, EvidenceClass
from shared.models.audit_rendering import is_not_evaluated


logger = getLogger(__name__)
console = Console()


# ADR-113: how a verdict was established, rendered for the gap report.
_EVIDENCE_STYLES = {
    EvidenceClass.PROVEN: "[green]proven[/green]",
    EvidenceClass.JUDGED: "[yellow]judged[/yellow]",
    EvidenceClass.ATTESTED: "[magenta]needs human[/magenta]",
}


# #956: a check that could not run established no verdict, so it has no
# evidence class to show and is not a violation of its severity.
_NOT_EVALUATED_SEVERITY = "[bold yellow]NOT EVALUATED[/bold yellow]"
_NOT_EVALUATED_EVIDENCE = "[yellow]unavailable[/yellow]"


# ID: 7b5e2a91-3c64-4d8f-9a1e-6f2b8c4d7e03
def _evidence_label(evidence_class: EvidenceClass) -> str:
    """Render a finding's evidence class (ADR-113) for the Rich tables."""
    return _EVIDENCE_STYLES.get(evidence_class, str(evidence_class))


def _row_labels(finding: AuditFinding, severity_styles: dict) -> tuple[str, str]:
    """Severity and evidence cells; a not-evaluated finding shows as such (#956)."""
    if is_not_evaluated(finding):
        return _NOT_EVALUATED_SEVERITY, _NOT_EVALUATED_EVIDENCE
    return (
        severity_styles.get(finding.severity, str(finding.severity)),
        _evidence_label(finding.evidence_class),
    )


# ID: b0dc9c82-dd40-4970-94e8-911fd3354930
def print_verbose_findings(findings: list[AuditFinding]) -> None:
    """Prints every single finding in a detailed table for verbose output."""
    table = Table(
        title="[bold]Verbose Audit Findings[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Severity", style="cyan")
    table.add_column("Evidence", style="green")  # ADR-113
    table.add_column("Check ID", style="magenta")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("File:Line", style="yellow")
    severity_styles = {
        AuditSeverity.BLOCK: "[bold red]BLOCK[/bold red]",
        AuditSeverity.HIGH: "[bold yellow]HIGH[/bold yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }
    for finding in findings:
        location = str(finding.file_path or "")
        if finding.line_number:
            location += f":{finding.line_number}"
        # ADR-098 D3: surface iceberg scale on quality-gate findings
        issue_count = finding.context.get("issue_count")
        if isinstance(issue_count, int) and issue_count > 1 and finding.file_path:
            location += f" (x{issue_count})"
        severity_cell, evidence_cell = _row_labels(finding, severity_styles)
        table.add_row(
            severity_cell,
            evidence_cell,
            escape(finding.check_id),
            escape(finding.message),
            escape(location),
        )
    console.print(table)


# ID: cac19f77-d41c-4493-aeaa-7eb5af07cd90
def print_summary_findings(findings: list[AuditFinding]) -> None:
    """Groups findings by check ID only and prints a summary table."""
    grouped_findings: dict[tuple[str, AuditSeverity], list[AuditFinding]] = defaultdict(
        list
    )
    for f in findings:
        key = (f.check_id, f.severity)
        grouped_findings[key].append(f)
    table = Table(
        title="[bold]Audit Findings Summary[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Severity", style="cyan")
    table.add_column("Evidence", style="green")  # ADR-113
    table.add_column("Check ID", style="magenta")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("Occurrences", style="yellow", justify="right")
    severity_styles = {
        AuditSeverity.BLOCK: "[bold red]BLOCK[/bold red]",
        AuditSeverity.HIGH: "[bold yellow]HIGH[/bold yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }
    sorted_items = sorted(
        grouped_findings.items(),
        key=lambda item: (item[0][1], item[0][0]),
        reverse=True,
    )
    for (check_id, severity), finding_list in sorted_items:
        representative_message = finding_list[0].message
        severity_cell, evidence_cell = _row_labels(finding_list[0], severity_styles)
        table.add_row(
            severity_cell,
            evidence_cell,
            escape(check_id),
            escape(representative_message),
            str(len(finding_list)),
        )
    console.print(table)
    console.print("\n[dim]Run with '--verbose' to see all individual locations.[/dim]")


# ID: f3a8c1d5-6e29-4b7f-9c3a-1d8e5f2a9b04
def print_hidden_findings_hint(
    all_findings: list[AuditFinding],
    filtered_findings: list[AuditFinding],
    min_severity: AuditSeverity,
) -> None:
    """Tell the user how many findings the --severity floor is hiding.

    The Audit Overview severity table (rendered from ``all_findings``) counts
    every finding, including those below the floor — but neither
    ``print_summary_findings`` nor ``print_verbose_findings`` ever sees them,
    since callers pre-filter to ``filtered_findings`` before printing. Without
    this, a finding count like "INFO 92" appears in the overview with no
    itemization and no indication that lowering --severity would reveal it —
    the existing "Run with '--verbose'" hint is misleading here, since
    --verbose alone shows nothing for a severity already filtered out.
    """
    hidden = len(all_findings) - len(filtered_findings)
    if hidden <= 0 or min_severity <= AuditSeverity.INFO:
        return
    console.print(
        f"[dim]{hidden} additional finding(s) below --severity {min_severity} "
        "are not shown. Run with --severity info --verbose to see them.[/dim]"
    )


_CHECK_TO_TASK: dict[str, str] = {
    "test": "test_generation",
    "coverage": "test_generation",
    "docstring": "code_modification",
    "linkage": "code_modification",
    "architecture": "code_modification",
    "agent": "code_modification",
    "safety": "code_modification",
    "ai": "code_modification",
    "purity": "code_modification",
    "modularity": "code_modification",
    "logic": "code_modification",
    "workflow": "code_modification",
}
_SKIP_FILE_PREFIXES = ("DB", "none", "None", "System", "/")
_CALL_PATTERNS = {"make_request_async", "make_request", "invoke", "print", "logger"}


def _is_real_file_path(file_path: str) -> bool:
    """Return True only for real source file paths."""
    if not file_path:
        return False
    if any(file_path.startswith(p) for p in _SKIP_FILE_PREFIXES):
        return False
    if not file_path.endswith(".py"):
        return False
    return True


def _infer_task_type(check_id: str) -> str:
    """Map check_id prefix to the most appropriate context build task type."""
    check_lower = check_id.lower()
    for prefix, task in _CHECK_TO_TASK.items():
        if check_lower.startswith(prefix):
            return task
    return "code_modification"


def _extract_symbol(finding: AuditFinding) -> str | None:
    """
    Try to extract a symbol name from a finding.

    Priority:
    1. context["symbol_key"] / context["symbol_path"]
    2. context["name"] / context["symbol_name"]
    3. Parse message — only class/function names, not call patterns
    """
    ctx = finding.context or {}
    symbol_key = ctx.get("symbol_key") or ctx.get("symbol_path")
    if symbol_key:
        sym_name = str(symbol_key).split("::")[-1].strip()
        if sym_name and sym_name not in _CALL_PATTERNS:
            return sym_name
    name = ctx.get("name") or ctx.get("symbol_name")
    if name and str(name).strip() not in _CALL_PATTERNS:
        return str(name).strip()
    match = re.search("'([A-Za-z_][A-Za-z0-9_]*)'", finding.message or "")
    if match:
        candidate = match.group(1)
        if candidate not in _CALL_PATTERNS:
            return candidate
    return None


# ID: 91657aab-4dc3-478b-9563-ce344e823e15
def print_context_build_hints(findings: list[AuditFinding]) -> None:
    """
    Print exact context build commands for actionable findings.

    Bridges audit output directly to the AI workflow with zero manual translation.
    Only emits hints for ERROR/WARNING findings with real .py file paths,
    deduplicated by (file, symbol) pair.
    """
    actionable = [
        f
        for f in findings
        if _is_real_file_path(str(f.file_path or ""))
        and f.severity >= AuditSeverity.HIGH
    ]
    if not actionable:
        return
    seen: set[tuple[str, str | None]] = set()
    hints: list[tuple[AuditFinding, str | None]] = []
    for f in actionable:
        symbol = _extract_symbol(f)
        key = (str(f.file_path), symbol)
        if key not in seen:
            seen.add(key)
            hints.append((f, symbol))
    console.print()
    console.print(
        Panel(
            f"[dim]{len(hints)} actionable location(s). Run the command below for each, then paste the output to Claude.[/dim]",
            title="[bold cyan]💡 AI Workflow — Next Steps[/bold cyan]",
            expand=False,
        )
    )
    severity_icon = {
        AuditSeverity.BLOCK: "[bold red]❌ BLOCK[/bold red]",
        AuditSeverity.HIGH: "[bold yellow]⚠️  HIGH [/bold yellow]",
    }
    for finding, symbol in hints:
        file_path = str(finding.file_path)
        task = _infer_task_type(finding.check_id)
        icon = severity_icon.get(finding.severity, "")
        console.print(f"\n  {icon} [magenta]{escape(finding.check_id)}[/magenta]")
        console.print(f"  [dim]{escape(finding.message[:100])}[/dim]")
        if symbol:
            console.print(
                f"\n  [green]core-admin context build \\\n      --file {file_path} \\\n      --symbol {symbol} \\\n      --task {task} \\\n      --output var/context_for_claude.md[/green]"
            )
        else:
            console.print(
                f"\n  [green]core-admin context build \\\n      --file {file_path} \\\n      --task {task} \\\n      --output var/context_for_claude.md[/green]"
            )
    console.print()
