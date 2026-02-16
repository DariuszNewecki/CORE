# src/body/cli/resources/code/audit.py
# ID: e4570c9b-6eab-4ee5-86d2-7a772532dbc3
"""Constitutional Audit CLI Command.

Runs the full constitutional self-audit and renders human-readable results.

Updated (V2.3.0)
- Properly converts raw Auditor findings into renderer objects, fixing:
  AttributeError: 'str' object has no attribute 'severity'
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from body.cli.commands.check.converters import parse_min_severity
from body.cli.logic.audit_renderer import AuditStats, render_detail, render_overview
from body.services.file_service import FileService
from body.services.service_registry import service_registry
from mind.governance.audit_postprocessor import apply_entry_point_downgrade_and_report
from mind.governance.auditor import ConstitutionalAuditor
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.models import AuditFinding, AuditSeverity

from .hub import app


console = Console()

REPORTS_DIR = "reports"
FINDINGS_FILE = "reports/audit_findings.json"
EVIDENCE_FILE = "reports/audit/latest_audit.json"


def _to_audit_finding(raw: dict | AuditFinding) -> AuditFinding:
    """Safely convert a dictionary finding into a structured AuditFinding object."""
    if isinstance(raw, AuditFinding):
        return raw

    severity_map = {
        "info": AuditSeverity.INFO,
        "warning": AuditSeverity.WARNING,
        "error": AuditSeverity.ERROR,
        "blocking": AuditSeverity.ERROR,
        "reporting": AuditSeverity.WARNING,
        "advisory": AuditSeverity.INFO,
    }

    raw_severity = str(raw.get("severity", "info")).lower()
    severity = severity_map.get(raw_severity, AuditSeverity.INFO)

    return AuditFinding(
        check_id=raw.get("check_id") or raw.get("rule_id") or "unknown",
        severity=severity,
        message=raw.get("message", ""),
        file_path=raw.get("file_path"),
        line_number=raw.get("line_number"),
        context=raw.get("context", {}),
    )


# ID: 7c8e4c09-85e8-43cf-be31-808e55cc71cd
@app.command("audit")
@core_command(dangerous=False)
# ID: fc800d58-6848-4232-a68d-d4bbfc2768c4
async def audit_command(
    ctx: typer.Context,
    target: Path = typer.Argument(Path("src"), help="Directory or file to audit."),
    severity: str = typer.Option(
        "warning",
        "--severity",
        "-s",
        help="Minimum severity level.",
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show every individual finding.",
    ),
) -> None:
    """Run the full constitutional self-audit on the codebase."""
    min_severity = parse_min_severity(severity)

    core_context = ctx.obj
    file_service = FileService(core_context.git_service.repo_path)

    # Ensure directories exist
    file_service.ensure_dir("reports/audit")

    # 1) Execute the headless audit
    with activity_run("constitutional_audit") as run:
        # JIT session injection for the Auditor
        async with service_registry.session() as session:
            core_context.auditor_context.db_session = session
            auditor = ConstitutionalAuditor(core_context.auditor_context)

            start_time = time.perf_counter()
            results = await auditor.run_full_audit_async()
            duration = time.perf_counter() - start_time

            # Clean up session ref
            core_context.auditor_context.db_session = None

        # 2) Conversion & persistence
        raw_findings = results["findings"]
        all_findings = [_to_audit_finding(f) for f in raw_findings]

        findings_dicts = [f.as_dict() for f in all_findings]
        file_service.write_file(FINDINGS_FILE, json.dumps(findings_dicts, indent=2))

        apply_entry_point_downgrade_and_report(
            findings=findings_dicts,
            symbol_index={},  # In-memory index could be loaded here
            reports_dir=Path(core_context.git_service.repo_path) / REPORTS_DIR,
            file_service=file_service,
            repo_root=Path(core_context.git_service.repo_path),
        )

        evidence = {
            "audit_id": run.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "passed": results["passed"],
            "findings_count": len(all_findings),
            "executed_rules": sorted(list(results["executed_rule_ids"])),
        }
        file_service.write_file(EVIDENCE_FILE, json.dumps(evidence, indent=2))

    # 3) Presentation
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    stats = results["stats"]
    audit_stats = AuditStats(
        total_rules=stats.get("total_executable_rules", 0),
        executed_rules=stats.get("executed_dynamic_rules", 0),
        coverage_percent=stats.get("coverage_percent", 0),
    )

    render_overview(console, all_findings, audit_stats, duration, results["passed"])

    if filtered_findings and verbose:
        render_detail(console, filtered_findings)

    if not results["passed"]:
        raise typer.Exit(1)
