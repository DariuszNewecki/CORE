# src/body/cli/resources/code/audit.py
# ID: e4570c9b-6eab-4ee5-86d2-7a772532dbc3
"""Constitutional Audit CLI Command.

Runs the full constitutional self-audit and renders human-readable results.

Updated (V2.4.0)
- Restored --rule/--policy filtering support (Hybrid Mode).
- If filters are used, Evidence Artifacts are SKIPPED to prevent
  partial audits from corrupting the compliance ledger.
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
from mind.governance.filtered_audit import run_filtered_audit
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


@app.command("audit")
@core_command(dangerous=False)
# ID: dcde428e-8586-48c7-94e1-be353a136ea0
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
    rule: list[str] = typer.Option(
        [], "--rule", "-r", help="Filter by specific rule IDs."
    ),
    policy: list[str] = typer.Option(
        [], "--policy", "-p", help="Filter by specific policy IDs."
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show every individual finding.",
    ),
) -> None:
    """
    Run the constitutional self-audit on the codebase.

    Modes:
    1. Full Audit (default): Runs all rules, generates official evidence artifacts.
    2. Filtered Audit (with --rule/--policy): Runs subset, SKIPS evidence generation.
    """
    min_severity = parse_min_severity(severity)
    core_context = ctx.obj
    file_service = FileService(core_context.git_service.repo_path)

    # Determine Mode
    is_filtered = bool(rule or policy)
    mode_label = "Filtered" if is_filtered else "Full Constitutional"

    # Ensure directories exist
    file_service.ensure_dir("reports/audit")

    # 1) Execute the Audit
    with activity_run("constitutional_audit") as run:
        # JIT session injection for the Auditor
        async with service_registry.session() as session:
            core_context.auditor_context.db_session = session
            auditor = ConstitutionalAuditor(core_context.auditor_context)

            start_time = time.perf_counter()

            if is_filtered:
                # Surgical Path: Delegate to Filtered Audit Engine
                console.print(
                    f"[bold cyan]🔍 Running {mode_label} Audit...[/bold cyan]"
                )
                if rule:
                    console.print(f"   Rules: {', '.join(rule)}")

                # Load KG first
                await core_context.auditor_context.load_knowledge_graph()

                raw_findings, executed_ids, stats_dict = await run_filtered_audit(
                    core_context.auditor_context, rule_ids=rule, policy_ids=policy
                )

                # Normalize stats structure
                results = {
                    "findings": raw_findings,
                    "stats": {
                        "total_executable_rules": stats_dict["total_rules"],
                        "executed_dynamic_rules": stats_dict["executed_rules"],
                        "coverage_percent": 0,  # Not applicable in filtered mode
                    },
                    "executed_rule_ids": executed_ids,
                    "passed": True,  # Re-calculated below
                }
            else:
                # Standard Path: Full Audit
                console.print(
                    f"[bold cyan]⚖️  Running {mode_label} Audit...[/bold cyan]"
                )
                results = await auditor.run_full_audit_async()

            duration = time.perf_counter() - start_time

            # Clean up session ref
            core_context.auditor_context.db_session = None

        # 2) Conversion
        # Handle mixed types (dicts vs objects) from different engines
        raw_findings_list = results["findings"]
        all_findings = []

        for f in raw_findings_list:
            if hasattr(f, "as_dict"):
                f = f.as_dict()
            all_findings.append(_to_audit_finding(f))

        # 3) Persistence (ONLY FOR FULL AUDITS)
        if not is_filtered:
            findings_dicts = [f.as_dict() for f in all_findings]
            file_service.write_file(FINDINGS_FILE, json.dumps(findings_dicts, indent=2))

            apply_entry_point_downgrade_and_report(
                findings=findings_dicts,
                symbol_index={},
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
        else:
            console.print(
                "[dim]Note: Evidence artifacts skipped for filtered audit.[/dim]"
            )

    # 4) Presentation
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

    # Re-calculate pass/fail for the filtered set
    blocking_errors = [f for f in all_findings if f.severity == AuditSeverity.ERROR]
    passed = len(blocking_errors) == 0

    verdict = results.get("verdict")
    verdict_str = verdict.value if verdict else ("PASS" if passed else "FAIL")
    render_overview(
        console, all_findings, audit_stats, duration, passed, verdict_str=verdict_str
    )

    if filtered_findings and verbose:
        render_detail(console, filtered_findings)

    if not passed:
        raise typer.Exit(1)
