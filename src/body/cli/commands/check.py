# src/body/cli/commands/check.py
"""
Registers and implements the verb-based 'check' command group.
Refactored to use the Constitutional CLI Framework (@core_command).
Handles UI presentation for audit results.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from body.cli.logic.body_contracts_checker import check_body_contracts
from body.cli.logic.diagnostics_policy import policy_coverage
from mind.enforcement.audit import lint, run_audit_workflow, test_system

# Engine-based auditor (rules -> engines)
from mind.logic.auditor import ConstitutionalAuditor as EngineConstitutionalAuditor
from shared.action_types import ActionResult
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_utils import get_repo_root


logger = getLogger(__name__)
console = Console()

check_app = typer.Typer(
    help="Read-only validation and health checks.", no_args_is_help=True
)

# Evidence artifact written by legacy governance auditor
_LEGACY_AUDIT_EVIDENCE_PATH = (
    get_repo_root() / "reports" / "audit" / "latest_audit.json"
)


def _print_verbose_findings(findings: list[AuditFinding]) -> None:
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
    console.print(table)


def _print_summary_findings(findings: list[AuditFinding]) -> None:
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

    # Sort by severity (highest first), then by check_id
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

    console.print(table)
    console.print("\n[dim]Run with '--verbose' to see all individual locations.[/dim]")


def _parse_min_severity(severity: str) -> AuditSeverity:
    try:
        return AuditSeverity[severity.upper()]
    except KeyError as exc:
        raise typer.BadParameter(
            f"Invalid severity level '{severity}'. Must be 'info', 'warning', or 'error'."
        ) from exc


def _severity_from_string(value: str | None) -> AuditSeverity:
    if not value:
        return AuditSeverity.ERROR
    v = value.strip().lower()
    if v == "info":
        return AuditSeverity.INFO
    if v == "warning":
        return AuditSeverity.WARNING
    if v == "error":
        return AuditSeverity.ERROR
    return AuditSeverity.ERROR


def _iter_target_files(target: Path) -> list[Path]:
    """
    Resolve target into a list of files to audit.

    - If target is a file: audit that file
    - If target is a directory: audit all *.py files under it
    """
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(p for p in target.rglob("*.py") if p.is_file())
    return []


def _convert_engine_findings_to_audit_findings(
    *,
    file_path: Path,
    engine_findings: list[dict],
    tag_check_ids: bool,
) -> list[AuditFinding]:
    """
    Convert engine-based auditor findings (dicts) to AuditFinding objects
    so existing UI rendering can be reused.

    If tag_check_ids=True, check_id will be prefixed with "v2:" to make it
    obvious in merged outputs which system produced the finding.
    """
    converted: list[AuditFinding] = []
    for f in engine_findings:
        rule_id = str(f.get("rule_id") or "unknown")
        engine = str(f.get("engine") or "").strip()
        message = str(f.get("message") or "Violation")
        severity = _severity_from_string(f.get("severity"))

        check_id = f"v2:{rule_id}" if tag_check_ids else rule_id
        if engine:
            message = f"[{engine}] {message}"

        converted.append(
            AuditFinding(
                check_id=check_id,
                severity=severity,
                message=message,
                file_path=str(file_path),
                line_number=None,
            )
        )
    return converted


def _read_legacy_executed_ids_from_evidence() -> set[str]:
    """
    Best-effort: read legacy auditor evidence artifact to learn which checks/rules executed.
    Returns empty set if evidence is missing or invalid.
    """
    try:
        if not _LEGACY_AUDIT_EVIDENCE_PATH.exists():
            return set()
        payload = json.loads(_LEGACY_AUDIT_EVIDENCE_PATH.read_text(encoding="utf-8"))
        executed = payload.get("executed_checks", [])
        if not isinstance(executed, list):
            return set()
        return {str(x).strip() for x in executed if isinstance(x, str) and x.strip()}
    except Exception:
        return set()


def _print_migration_delta(*, legacy_executed: set[str], v2_rule_ids: set[str]) -> None:
    """
    Print a small migration delta so you can see what remains to be migrated.
    """
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

    console.print(table)

    # Show a small sample for actionability (avoid spam)
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

    console.print(details)


@check_app.command("audit")
@core_command(dangerous=False)
# ID: ca09d5e2-b0af-4ed2-9c8b-9dcb515e3c00
async def audit_cmd(
    ctx: typer.Context,
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all individual findings instead of a summary.",
    ),
) -> None:
    """
    Run the full constitutional self-audit (legacy check-class system).
    """
    core_context: CoreContext = ctx.obj

    passed, all_findings = await run_audit_workflow(core_context)

    min_severity = _parse_min_severity(severity)
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    unassigned_count = len(
        [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
    )

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")

    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]

    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    summary_table.add_row("Unassigned Symbols:", f"[cyan]{unassigned_count}[/cyan]")

    title = "✅ AUDIT PASSED" if passed else "❌ AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            _print_verbose_findings(filtered_findings)
        else:
            _print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)


@check_app.command("audit-v2")
@core_command(dangerous=False)
# ID: 6c7ab9b7-78a3-4b75-8e9e-2ab6a0f3d3bf
async def audit_v2_cmd(
    ctx: typer.Context,
    target: Path = typer.Argument(
        Path("src"),
        help="File or directory to audit. If a directory, audits all *.py under it.",
    ),
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all individual findings instead of a summary.",
    ),
    include_llm: bool = typer.Option(
        False,
        "--include-llm-v2",
        help="Include v2 findings from LLM engines (default: off).",
    ),
) -> None:
    """
    Run the engine-based constitutional audit (rules -> engines).
    """
    _ = ctx

    min_severity = _parse_min_severity(severity)

    files = _iter_target_files(target)
    if not files:
        console.print(f"[bold red]No audit targets found at: {target}[/bold red]")
        raise typer.Exit(code=1)

    auditor = EngineConstitutionalAuditor()

    all_findings: list[AuditFinding] = []
    for file_path in files:
        engine_findings = auditor.audit_file(file_path)

        if not include_llm:
            engine_findings = [
                f
                for f in engine_findings
                if str(f.get("engine") or "").strip().lower() not in {"llm_gate", "llm"}
            ]

        all_findings.extend(
            _convert_engine_findings_to_audit_findings(
                file_path=file_path,
                engine_findings=engine_findings,
                tag_check_ids=False,
            )
        )

    passed = not any(f.severity.is_blocking for f in all_findings)
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")

    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]

    summary_table.add_row("Files Audited:", str(len(files)))
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")

    title = "✅ AUDIT V2 PASSED" if passed else "❌ AUDIT V2 FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            _print_verbose_findings(filtered_findings)
        else:
            _print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)


@check_app.command("audit-hybrid")
@core_command(dangerous=False)
# ID: 8cfe7d3f-3a98-4fb6-8c75-6cba52d7bf42
async def audit_hybrid_cmd(
    ctx: typer.Context,
    target: Path = typer.Argument(
        Path("src"),
        help="File or directory to audit with v2. Legacy audit is always global.",
    ),
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Filter findings by minimum severity level (info, warning, error).",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show all individual findings instead of a summary.",
    ),
    include_llm_v2: bool = typer.Option(
        False,
        "--include-llm-v2",
        help="Include v2 findings from LLM engines (default: off; use legacy for LLM checks).",
    ),
) -> None:
    """
    Run both audit models and produce a migration delta.

    Intended migration behavior:
    - Legacy audit remains the authority for non-file-scoped checks and (by default) LLM checks.
    - V2 audit becomes the authority for deterministic, file-scoped checks.
    """
    core_context: CoreContext = ctx.obj
    min_severity = _parse_min_severity(severity)

    # --- Run legacy audit first (global/system checks + legacy mechanics) ---
    legacy_passed, legacy_findings = await run_audit_workflow(core_context)
    legacy_executed_ids = _read_legacy_executed_ids_from_evidence()

    # --- Run v2 on target files (file-scoped rules -> engines) ---
    files = _iter_target_files(target)
    if not files:
        console.print(f"[bold red]No audit targets found at: {target}[/bold red]")
        raise typer.Exit(code=1)

    auditor = EngineConstitutionalAuditor()
    v2_findings: list[AuditFinding] = []
    v2_rule_ids: set[str] = set()

    for file_path in files:
        raw = auditor.audit_file(file_path)

        if not include_llm_v2:
            raw = [
                f
                for f in raw
                if str(f.get("engine") or "").strip().lower() not in {"llm_gate", "llm"}
            ]

        for f in raw:
            rid = str(f.get("rule_id") or "").strip()
            if rid:
                v2_rule_ids.add(rid)

        v2_findings.extend(
            _convert_engine_findings_to_audit_findings(
                file_path=file_path,
                engine_findings=raw,
                tag_check_ids=True,  # make hybrid output explicit
            )
        )

    # --- Merge findings for display ---
    all_findings = list(legacy_findings) + v2_findings
    passed = legacy_passed and not any(f.severity.is_blocking for f in v2_findings)

    # Filter for display
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    # Summary panel
    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")

    all_errors = [f for f in all_findings if f.severity.is_blocking]
    all_warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]

    legacy_errors = [f for f in legacy_findings if f.severity.is_blocking]
    v2_errors = [f for f in v2_findings if f.severity.is_blocking]

    summary_table.add_row("Legacy findings:", str(len(legacy_findings)))
    summary_table.add_row("V2 findings:", str(len(v2_findings)))
    summary_table.add_row("Files audited (v2):", str(len(files)))
    summary_table.add_row("Errors (total):", f"[red]{len(all_errors)}[/red]")
    summary_table.add_row("Warnings (total):", f"[yellow]{len(all_warnings)}[/yellow]")
    summary_table.add_row("Errors (legacy):", f"[red]{len(legacy_errors)}[/red]")
    summary_table.add_row("Errors (v2):", f"[red]{len(v2_errors)}[/red]")

    title = "✅ HYBRID AUDIT PASSED" if passed else "❌ HYBRID AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    # Findings output
    if filtered_findings:
        if verbose:
            _print_verbose_findings(filtered_findings)
        else:
            _print_summary_findings(filtered_findings)

    # Migration delta
    _print_migration_delta(legacy_executed=legacy_executed_ids, v2_rule_ids=v2_rule_ids)

    if not passed:
        raise typer.Exit(1)


@check_app.command("lint")
@core_command(dangerous=False)
# ID: 8428c471-1a01-4327-9640-52987ef7130d
def lint_cmd(ctx: typer.Context) -> None:
    """
    Check code formatting and quality using Black and Ruff.
    """
    _ = ctx
    lint()


@check_app.command("tests")
@core_command(dangerous=False)
# ID: 1e60b497-4db8-4d00-96f2-945ac2d096da
def tests_cmd(ctx: typer.Context) -> None:
    """
    Run the project test suite via pytest.
    """
    _ = ctx
    test_system()


@check_app.command("diagnostics")
@core_command(dangerous=False)
# ID: 9f9ebe73-c1b6-478f-aa52-21adcb64f1e0
def diagnostics_cmd(ctx: typer.Context) -> None:
    """
    Audit the constitution for policy coverage and structural integrity.
    """
    _ = ctx
    policy_coverage()


@check_app.command("system")
@core_command(dangerous=False)
# ID: 461df3d1-5724-44be-a11e-691b9d88d5e0
async def system_cmd(ctx: typer.Context) -> None:
    """
    Run all system health checks: Lint, Tests, and Constitutional Audit.
    """
    console.rule("[bold cyan]1. Code Quality (Lint)[/bold cyan]")
    lint()

    console.rule("[bold cyan]2. System Integrity (Tests)[/bold cyan]")
    test_system()

    console.rule("[bold cyan]3. Constitutional Compliance (Audit)[/bold cyan]")
    await audit_cmd(ctx)


@check_app.command("body-ui")
@core_command(dangerous=False)
# ID: 3a985f2b-4d76-4c28-9f1e-8e3d2a7b6c9d
async def check_body_ui_cmd(ctx: typer.Context) -> None:
    """
    Check for Body layer UI contract violations (print, rich usage, os.environ).

    Body modules must be HEADLESS.
    """
    _ = ctx
    console.print("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")

    result: ActionResult = await check_body_contracts()

    if not result.ok:
        violations = result.data.get("violations", [])
        console.print(f"\n[red]❌ Found {len(violations)} contract violations:[/red]\n")

        # Group by file for cleaner output
        by_file: dict[str, list[dict]] = {}
        for v in violations:
            path = v.get("file", "unknown")
            by_file.setdefault(path, []).append(v)

        for path, file_violations in by_file.items():
            console.print(f"[bold]{path}[/bold]:")
            for v in file_violations:
                rule = v.get("rule_id", "unknown")
                msg = v.get("message", "")
                line = v.get("line")
                loc = f"line {line}" if line else "general"
                console.print(f"  - [{rule}] {msg} ({loc})")
            console.print()

        console.print(
            "[yellow]💡 Run 'core-admin fix body-ui --write' to auto-fix.[/yellow]"
        )
        raise typer.Exit(1)

    console.print("[green]✅ Body contracts compliant.[/green]")
