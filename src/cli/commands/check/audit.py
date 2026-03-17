# src/cli/commands/check/audit.py

"""
Core audit commands: audit.
Refactored to use the canonical CoreContext provided by the framework.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

from cli.commands.check.converters import parse_min_severity
from cli.commands.check.formatters import (
    print_summary_findings,
    print_verbose_findings,
)
from mind.governance.auditor import ConstitutionalAuditor
from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


console = Console()
logger = getLogger(__name__)


def _to_audit_finding(raw: dict) -> AuditFinding:
    severity_map = {
        "info": AuditSeverity.INFO,
        "warning": AuditSeverity.WARNING,
        "error": AuditSeverity.ERROR,
    }
    raw_severity = str(raw.get("severity", "info")).lower()
    severity = severity_map.get(raw_severity, AuditSeverity.INFO)
    return AuditFinding(
        check_id=raw.get("check_id", "unknown"),
        severity=severity,
        message=raw.get("message", ""),
        file_path=raw.get("file_path"),
        line_number=raw.get("line_number"),
        context=raw.get("context", {}),
    )


async def _persist_findings_to_db(findings: list[AuditFinding]) -> None:
    """Persist audit findings to core.audit_findings (DB SSOT)."""
    logger.info("_persist_findings_to_db called with %d findings.", len(findings))

    if not findings:
        logger.warning("No findings to persist — skipping.")
        return

    rows = [
        {
            "check_id": f.check_id,
            "severity": (
                f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            ),
            "message": f.message,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "context": json.dumps(f.context) if f.context else None,
        }
        for f in findings
    ]

    logger.info("Persisting %d rows to core.audit_findings.", len(rows))

    try:
        async with get_session() as session:
            await session.execute(text("TRUNCATE TABLE core.audit_findings"))
            await session.execute(
                text(
                    """
                    INSERT INTO core.audit_findings
                        (check_id, severity, message, file_path, line_number, context)
                    VALUES
                        (:check_id, :severity, :message, :file_path,
                         :line_number, cast(:context as jsonb))
                    """
                ),
                rows,
            )
            await session.commit()
        logger.info("Persisted %d findings to core.audit_findings.", len(rows))
    except Exception as exc:
        logger.error("Failed to persist findings to DB: %s", exc, exc_info=True)


@core_command(dangerous=False)
# ID: 2a6833cf-af2f-432f-8423-dad36e20d936
async def audit_cmd(
    ctx: typer.Context,
    target: Path = typer.Argument(Path("src"), help="File or directory to audit."),
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Minimum severity level.",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show individual findings."
    ),
) -> None:
    """
    Run the full constitutional self-audit.
    """
    min_severity = parse_min_severity(severity)

    auditor_context = ctx.obj.auditor_context
    auditor = ConstitutionalAuditor(auditor_context)

    # Execute audit (Mind layer — pure, no I/O)
    result = await auditor.run_full_audit_async()
    findings = result["findings"]
    logger.info("Audit returned %d findings.", len(findings))

    all_findings = [
        _to_audit_finding(f.as_dict() if hasattr(f, "as_dict") else f) for f in findings
    ]
    logger.info("Converted to %d AuditFinding objects.", len(all_findings))

    # Persist to DB SSOT (Body layer responsibility)
    await _persist_findings_to_db(all_findings)

    # Presentation
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]
    errors = [f for f in all_findings if f.severity.is_blocking]
    warnings = [f for f in all_findings if f.severity == AuditSeverity.WARNING]
    infos = [f for f in all_findings if f.severity == AuditSeverity.INFO]

    passed = result["passed"]

    summary_table = Table.grid(expand=True, padding=(0, 1))
    summary_table.add_row("Total Findings:", str(len(all_findings)))
    summary_table.add_row("Errors:", f"[red]{len(errors)}[/red]")
    summary_table.add_row("Warnings:", f"[yellow]{len(warnings)}[/yellow]")
    summary_table.add_row("Info:", f"[cyan]{len(infos)}[/cyan]")
    summary_table.add_row("Verdict:", f"[bold]{result['verdict'].value}[/bold]")

    title = "✅ AUDIT PASSED" if passed else "❌ AUDIT FAILED"
    style = "bold green" if passed else "bold red"
    console.print(Panel(summary_table, title=title, style=style, expand=False))

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    if not passed:
        raise typer.Exit(1)
