"""
Output formatters for audit results.

Handles Rich UI presentation of findings, summaries, and statistics.
All formatting logic lives here - keeps command code clean.
"""

from __future__ import annotations

import re
from collections import defaultdict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)
console = Console()


# ID: b0dc9c82-dd40-4970-94e8-911fd3354930
def print_verbose_findings(findings: list[AuditFinding]) -> None:
    """Prints every single finding in a detailed table for verbose output."""
    table = Table(
        title="[bold]Verbose Audit Findings[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Severity", style="cyan")
    table.add_column("Check ID", style="magenta")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("File:Line", style="yellow")
    severity_styles = {
        AuditSeverity.ERROR: "[bold red]ERROR[/bold red]",
        AuditSeverity.WARNING: "[bold yellow]WARNING[/bold yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }
    for finding in findings:
        location = str(finding.file_path or "")
        if finding.line_number:
            location += f":{finding.line_number}"
        table.add_row(
            severity_styles.get(finding.severity, str(finding.severity)),
            finding.check_id,
            finding.message,
            location,
        )
    logger.info(table)


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
    table.add_column("Check ID", style="magenta")
    table.add_column("Message", style="white", overflow="fold")
    table.add_column("Occurrences", style="yellow", justify="right")
    severity_styles = {
        AuditSeverity.ERROR: "[bold red]ERROR[/bold red]",
        AuditSeverity.WARNING: "[bold yellow]WARNING[/bold yellow]",
        AuditSeverity.INFO: "[dim]INFO[/dim]",
    }
    sorted_items = sorted(
        grouped_findings.items(),
        key=lambda item: (item[0][1], item[0][0]),
        reverse=True,
    )
    for (check_id, severity), finding_list in sorted_items:
        representative_message = finding_list[0].message
        table.add_row(
            severity_styles.get(severity, str(severity)),
            check_id,
            representative_message,
            str(len(finding_list)),
        )
    logger.info(table)
    logger.info("\n[dim]Run with '--verbose' to see all individual locations.[/dim]")


# ID: 5127f2bc-b6fc-4452-9b6d-1c0d7f828043
def print_audit_summary(
    *,
    passed: bool,
    errors: list[AuditFinding],
    warnings: list[AuditFinding],
    unassigned_count: int | None = None,
    title_prefix: str = "",
) -> None:
    """Print audit summary panel with pass/fail status."""
    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    if unassigned_count is not None:
        summary_table.add_row("Unassigned Symbols:", f"[cyan]{unassigned_count}[/cyan]")
    title = (
        f"✅ {title_prefix}AUDIT PASSED" if passed else f"❌ {title_prefix}AUDIT FAILED"
    )
    style = "bold green" if passed else "bold red"
    logger.info(Panel(summary_table, title=title, style=style, expand=False))


# ID: e76eccad-7bfe-4134-ae63-2e7be93f5536
def print_filtered_audit_summary(
    *,
    passed: bool,
    stats: dict,
    errors: list[AuditFinding],
    warnings: list[AuditFinding],
) -> None:
    """Print summary for filtered/focused audit runs."""
    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")
    summary_table.add_row("Total Rules:", str(stats["total_rules"]))
    summary_table.add_row("Filtered Rules:", str(stats["filtered_rules"]))
    summary_table.add_row("Executed Rules:", str(stats["executed_rules"]))
    summary_table.add_row("Failed Rules:", f"[red]{stats.get('failed_rules', 0)}[/red]")
    summary_table.add_row("", "")
    summary_table.add_row("Total Findings:", str(stats["total_findings"]))
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    title = "✅ FILTERED AUDIT PASSED" if passed else "❌ FILTERED AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    logger.info(Panel(summary_table, title=title, style=style, expand=False))


# ID: a6337eb6-9780-46a0-817c-0e02acd2d206
def print_executed_rules(executed_rules: set[str]) -> None:
    """Print list of executed rules."""
    if not executed_rules:
        return
    logger.info("\n[dim]Executed rules:[/dim]")
    for rule_id in sorted(executed_rules):
        logger.info("  [dim]• %s[/dim]", rule_id)


# ID: ea2aff39-6dec-4462-9dd0-c4b116125e0a
def print_migration_delta(*, legacy_executed: set[str], v2_rule_ids: set[str]) -> None:
    """Print migration delta showing legacy vs v2 coverage."""
    legacy_only = sorted(legacy_executed - v2_rule_ids)
    v2_only = sorted(v2_rule_ids - legacy_executed)
    overlap = sorted(legacy_executed & v2_rule_ids)
    table = Table(
        title="[bold]Migration Delta (Legacy vs Engine-Based)[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="yellow", justify="right")
    table.add_row("Legacy executed ids (evidence)", str(len(legacy_executed)))
    table.add_row("V2 rule ids (from findings)", str(len(v2_rule_ids)))
    table.add_row("Overlap", str(len(overlap)))
    table.add_row("Legacy-only", str(len(legacy_only)))
    table.add_row("V2-only", str(len(v2_only)))
    logger.info(table)

    def _sample(values: list[str], n: int = 15) -> str:
        if not values:
            return "-"
        shown = values[:n]
        more = len(values) - len(shown)
        suffix = f" (+{more} more)" if more > 0 else ""
        return ", ".join(shown) + suffix

    details = Table(
        title="[bold]Migration Candidates (Samples)[/bold]",
        show_header=True,
        header_style="bold magenta",
    )
    details.add_column("Category", style="cyan")
    details.add_column("Sample ids", style="white", overflow="fold")
    details.add_row("Legacy-only (candidate to migrate)", _sample(legacy_only))
    details.add_row("V2-only (new coverage not in legacy evidence)", _sample(v2_only))
    logger.info(details)


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
        name = str(symbol_key).split("::")[-1].strip()
        if name and name not in _CALL_PATTERNS:
            return name
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
        and f.severity >= AuditSeverity.WARNING
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
    logger.info(
        Panel(
            f"[dim]{len(hints)} actionable location(s). Run the command below for each, then paste the output to Claude.[/dim]",
            title="[bold cyan]💡 AI Workflow — Next Steps[/bold cyan]",
            expand=False,
        )
    )
    severity_icon = {
        AuditSeverity.ERROR: "[bold red]❌ ERROR[/bold red]",
        AuditSeverity.WARNING: "[bold yellow]⚠️  WARN [/bold yellow]",
    }
    for finding, symbol in hints:
        file_path = str(finding.file_path)
        task = _infer_task_type(finding.check_id)
        icon = severity_icon.get(finding.severity, "")
        logger.info("\n  %s [magenta]%s[/magenta]", icon, finding.check_id)
        logger.info("  [dim]%s[/dim]", finding.message[:100])
        if symbol:
            logger.info(
                "\n  [green]core-admin context build \\\n      --file %s \\\n      --symbol %s \\\n      --task %s \\\n      --output var/context_for_claude.md[/green]",
                file_path,
                symbol,
                task,
            )
        else:
            logger.info(
                "\n  [green]core-admin context build \\\n      --file %s \\\n      --task %s \\\n      --output var/context_for_claude.md[/green]",
                file_path,
                task,
            )
    console.print()
