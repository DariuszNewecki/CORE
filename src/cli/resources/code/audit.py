# src/body/cli/resources/code/audit.py
# ID: e4570c9b-6eab-4ee5-86d2-7a772532dbc3
"""Constitutional Audit CLI Command.

Updated (V2.6.0)
- Fixed ImportError: Removed write_auto_ignored_reports (moved logic to Body).
- Fixed TypeError: Explicitly mapping AuditStats fields.
- Fully Compliant: CLI (Body) owns all side-effects (file writes).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from body.services.file_service import FileService
from body.services.service_registry import service_registry
from cli.commands.check.converters import parse_min_severity
from cli.logic.audit_renderer import AuditStats, render_detail, render_overview
from mind.governance.audit_postprocessor import apply_entry_point_downgrade
from mind.governance.audit_report_writer import build_auto_ignored_markdown
from mind.governance.auditor import ConstitutionalAuditor
from mind.governance.filtered_audit import run_filtered_audit
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.models import AuditFinding, AuditSeverity

from .hub import app


console = Console()

FINDINGS_FILE = "reports/audit_findings.json"
EVIDENCE_FILE = "reports/audit/latest_audit.json"
IGNORED_REPORT_MD = "reports/audit_auto_ignored.md"
IGNORED_REPORT_JSON = "reports/audit_auto_ignored.json"


def _to_audit_finding(raw: dict | AuditFinding) -> AuditFinding:
    if isinstance(raw, AuditFinding):
        return raw
    severity_map = {
        "info": AuditSeverity.INFO,
        "warning": AuditSeverity.WARNING,
        "error": AuditSeverity.ERROR,
    }
    severity = severity_map.get(
        str(raw.get("severity", "info")).lower(), AuditSeverity.INFO
    )
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
# ID: 67107783-c506-4634-a23c-c118e86befa8
async def audit_command(
    ctx: typer.Context,
    target: Path = typer.Argument(Path("src")),
    severity: str = typer.Option("warning", "--severity", "-s"),
    rule: list[str] = typer.Option([], "--rule", "-r"),
    policy: list[str] = typer.Option([], "--policy", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the constitutional self-audit."""
    min_severity = parse_min_severity(severity)
    core_context = ctx.obj
    file_service = FileService(core_context.git_service.repo_path)
    file_service.ensure_dir("reports/audit")

    with activity_run("constitutional_audit") as run:
        async with service_registry.session() as session:
            core_context.auditor_context.db_session = session
            auditor = ConstitutionalAuditor(core_context.auditor_context)
            start_time = time.perf_counter()

            if rule or policy:
                await core_context.auditor_context.load_knowledge_graph()
                raw_findings, executed_ids, stats_dict = await run_filtered_audit(
                    core_context.auditor_context, rule_ids=rule, policy_ids=policy
                )
                results = {
                    "findings": raw_findings,
                    "executed_rule_ids": executed_ids,
                    "passed": True,
                    "stats": stats_dict,
                }
            else:
                results = await auditor.run_full_audit_async()

            duration = time.perf_counter() - start_time
            core_context.auditor_context.db_session = None

        # 1. Ask the Mind to process the data (Pure logic)
        findings_raw = results["findings"]
        findings_dicts = [
            f.as_dict() if hasattr(f, "as_dict") else f for f in findings_raw
        ]
        processed_findings, ignored_data = apply_entry_point_downgrade(
            findings=findings_dicts, symbol_index={}
        )

        # 2. Body performs the execution (File writes)
        timestamp_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        if not (rule or policy):
            # Write Main Findings
            file_service.write_file(
                FINDINGS_FILE, json.dumps(processed_findings, indent=2)
            )

            # Write Ignored Reports (Body uses Mind's string builder)
            md_content = build_auto_ignored_markdown(timestamp_str, ignored_data)
            file_service.write_file(IGNORED_REPORT_MD, md_content)
            file_service.write_runtime_json(
                IGNORED_REPORT_JSON,
                {"generated_at": timestamp_str, "items": ignored_data},
            )

            # Record Evidence Ledger
            verdict = results.get("verdict")
            verdict_str = (
                verdict.value if verdict else ("PASS" if results["passed"] else "FAIL")
            )
            evidence = {
                "audit_id": run.run_id,
                "timestamp": timestamp_str,
                "passed": results["passed"],
                "findings_count": len(processed_findings),
                "executed_rules": sorted(list(results["executed_rule_ids"])),
                "verdict": verdict_str,
            }
            file_service.write_file(EVIDENCE_FILE, json.dumps(evidence, indent=2))

    # 3. Build AuditStats correctly
    raw_stats = results.get("stats", {})
    audit_stats = AuditStats(
        total_rules=raw_stats.get("total_executable_rules", 0),
        executed_rules=raw_stats.get("executed_dynamic_rules", 0),
        coverage_percent=raw_stats.get("coverage_percent", 0),
        total_declared_rules=raw_stats.get("total_declared_rules", 0),
        crashed_rules=raw_stats.get("crashed_rules", 0),
        unmapped_rules=raw_stats.get("unmapped_rules", 0),
        effective_coverage_percent=raw_stats.get("effective_coverage_percent", 0),
    )

    all_findings = [_to_audit_finding(f) for f in processed_findings]
    render_overview(console, all_findings, audit_stats, duration, results["passed"])
    if verbose:
        render_detail(console, [f for f in all_findings if f.severity >= min_severity])
    if not results["passed"]:
        raise typer.Exit(1)
