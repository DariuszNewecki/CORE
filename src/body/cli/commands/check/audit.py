# src/body/cli/commands/check/audit.py
# ID: d9e8be26-e5e2-4015-899b-8741adaa820c
"""Core audit commands: audit.

Updated (V2.3.0)
- CLI owns the reporting/persistence pipeline, preserving artifact creation.
- Mind layer (Auditor) remains headless.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from body.cli.commands.check.converters import parse_min_severity
from body.cli.logic.audit_renderer import AuditStats, render_detail, render_overview
from body.services.file_service import FileService
from body.services.service_registry import service_registry
from mind.governance.audit_postprocessor import apply_entry_point_downgrade

# from mind.governance.audit_postprocessor import apply_entry_point_downgrasde_and_report
from mind.governance.auditor import ConstitutionalAuditor
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.models import AuditFinding, AuditSeverity


console = Console()

REPORTS_DIR = "reports"
FINDINGS_FILE = "reports/audit_findings.json"
EVIDENCE_FILE = "reports/audit/latest_audit.json"


def _to_audit_finding(raw: dict | AuditFinding) -> AuditFinding:
    if isinstance(raw, AuditFinding):
        return raw

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


# ID: 2a6833cf-af2f-432e-8423-dad36e20d936
@core_command(dangerous=False)
# ID: 6bd8138b-ced6-48fa-b5db-afe51ba9903d
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
    """Run the full constitutional self-audit and persist evidence artifacts."""
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

            start_time = datetime.now(UTC)
            results = await auditor.run_full_audit_async()
            duration = (datetime.now(UTC) - start_time).total_seconds()

            # Clean up session ref
            core_context.auditor_context.db_session = None

        # Extract verdict early — needed by both persistence and presentation
        verdict = results.get("verdict")
        verdict_str = (
            verdict.value if verdict else ("PASS" if results["passed"] else "FAIL")
        )

        # 2) Persistence (CLI owns this)
        findings = results["findings"]
        findings_dicts = [f.as_dict() if hasattr(f, "as_dict") else f for f in findings]

        # Write reports/audit_findings.json
        file_service.write_file(FINDINGS_FILE, json.dumps(findings_dicts, indent=2))

        # Post-processing (downgrade entry points and write processed report)
        apply_entry_point_downgrade(
            findings=findings_dicts,
            symbol_index={},  # Placeholder or load from reports/symbol_index.json
            reports_dir=Path(core_context.git_service.repo_path) / REPORTS_DIR,
            file_service=file_service,
            repo_root=Path(core_context.git_service.repo_path),
        )

        # Write reports/audit/latest_audit.json (Evidence Ledger)
        evidence = {
            "audit_id": run.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "passed": results["passed"],
            "findings_count": len(findings),
            "executed_rules": sorted(list(results["executed_rule_ids"])),
            "crashed_rules": sorted(list(results.get("crashed_rule_ids", set()))),
            "verdict": verdict_str,
        }
        file_service.write_file(EVIDENCE_FILE, json.dumps(evidence, indent=2))

    # 3) Presentation
    all_findings = [_to_audit_finding(f) for f in findings]
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    stats = results["stats"]
    audit_stats = AuditStats(
        total_rules=stats.get("total_executable_rules", 0),
        executed_rules=stats.get("executed_dynamic_rules", 0),
        coverage_percent=stats.get("coverage_percent", 0),
        total_declared_rules=stats.get("total_declared_rules", 0),
        crashed_rules=stats.get("crashed_rules", 0),
        unmapped_rules=stats.get("unmapped_rules", 0),
        effective_coverage_percent=stats.get("effective_coverage_percent", 0),
    )

    render_overview(
        console,
        all_findings,
        audit_stats,
        duration,
        results["passed"],
        verdict_str=verdict_str,
    )

    if filtered_findings and verbose:
        render_detail(console, filtered_findings)

    if not results["passed"]:
        raise typer.Exit(1)
