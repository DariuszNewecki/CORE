# src/body/cli/commands/check/audit.py
"""
Core audit commands: audit, audit-v2, audit-hybrid.

Constitutional compliance verification using legacy Check classes
and modern engine-based execution.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from body.cli.commands.check.converters import (
    convert_engine_findings_to_audit_findings,
    parse_min_severity,
    read_legacy_executed_ids_from_evidence,
)
from body.cli.commands.check.formatters import (
    print_audit_summary,
    print_migration_delta,
    print_summary_findings,
    print_verbose_findings,
)
from body.cli.commands.check.utils import iter_target_files
from mind.enforcement.audit import run_audit_workflow
from mind.logic.auditor import ConstitutionalAuditor as EngineConstitutionalAuditor
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.models import AuditSeverity


console = Console()


# ID: ca09d5e2-b0af-4ed2-9c8b-9dcb515e3c00
@core_command(dangerous=False)
# ID: bcdf6e1c-7976-4764-96b0-9a7ff66ae9e1
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

    min_severity = parse_min_severity(severity)
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    unassigned_count = len(
        [f for f in all_findings if f.check_id == "linkage.capability.unassigned"]
    )

    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]

    print_audit_summary(
        passed=passed,
        errors=errors,
        warnings=warnings,
        unassigned_count=unassigned_count,
    )

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)


# ID: 6c7ab9b7-78a3-4b75-8e9e-2ab6a0f3d3bf
@core_command(dangerous=False)
# ID: 158d9ea2-c2ae-488d-a581-52c84a0297e4
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

    min_severity = parse_min_severity(severity)

    files = iter_target_files(target)
    if not files:
        console.print(f"[bold red]No audit targets found at: {target}[/bold red]")
        raise typer.Exit(code=1)

    auditor = EngineConstitutionalAuditor()

    all_findings = []
    for file_path in files:
        engine_findings = auditor.audit_file(file_path)

        if not include_llm:
            engine_findings = [
                f
                for f in engine_findings
                if str(f.get("engine") or "").strip().lower() not in {"llm_gate", "llm"}
            ]

        all_findings.extend(
            convert_engine_findings_to_audit_findings(
                file_path=file_path,
                engine_findings=engine_findings,
                tag_check_ids=False,
            )
        )

    passed = not any(f.severity.is_blocking for f in all_findings)
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]

    # Custom summary for V2
    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")
    summary_table.add_row("Files Audited:", str(len(files)))
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")

    from rich.panel import Panel

    title = "✅ AUDIT V2 PASSED" if passed else "❌ AUDIT V2 FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)


# ID: 8cfe7d3f-3a98-4fb6-8c75-6cba52d7bf42
@core_command(dangerous=False)
# ID: df0b2239-db71-44e1-9012-522185ce5f8b
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
        help="Include v2 findings from LLM engines (default: off).",
    ),
) -> None:
    """
    Run both audit models and produce a migration delta.
    """
    core_context: CoreContext = ctx.obj
    min_severity = parse_min_severity(severity)

    # Run legacy audit
    legacy_passed, legacy_findings = await run_audit_workflow(core_context)
    legacy_executed_ids = read_legacy_executed_ids_from_evidence()

    # Run v2 on target files
    files = iter_target_files(target)
    if not files:
        console.print(f"[bold red]No audit targets found at: {target}[/bold red]")
        raise typer.Exit(code=1)

    auditor = EngineConstitutionalAuditor()
    v2_findings = []
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
            convert_engine_findings_to_audit_findings(
                file_path=file_path,
                engine_findings=raw,
                tag_check_ids=True,
            )
        )

    # Merge findings
    all_findings = list(legacy_findings) + v2_findings
    passed = legacy_passed and not any(f.severity.is_blocking for f in v2_findings)
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    # Display hybrid summary
    all_errors = [f for f in all_findings if f.severity.is_blocking]
    all_warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]
    legacy_errors = [f for f in legacy_findings if f.severity.is_blocking]
    v2_errors = [f for f in v2_findings if f.severity.is_blocking]

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_column(justify="left")
    summary_table.add_column(justify="right", style="bold")
    summary_table.add_row("Legacy findings:", str(len(legacy_findings)))
    summary_table.add_row("V2 findings:", str(len(v2_findings)))
    summary_table.add_row("Files audited (v2):", str(len(files)))
    summary_table.add_row("Errors (total):", f"[red]{len(all_errors)}[/red]")
    summary_table.add_row("Warnings (total):", f"[yellow]{len(all_warnings)}[/red]")
    summary_table.add_row("Errors (legacy):", f"[red]{len(legacy_errors)}[/red]")
    summary_table.add_row("Errors (v2):", f"[red]{len(v2_errors)}[/red]")

    from rich.panel import Panel

    title = "✅ HYBRID AUDIT PASSED" if passed else "❌ HYBRID AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    print_migration_delta(legacy_executed=legacy_executed_ids, v2_rule_ids=v2_rule_ids)

    if not passed:
        raise typer.Exit(1)
