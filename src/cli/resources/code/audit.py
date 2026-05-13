# src/cli/resources/code/audit.py
"""Constitutional Audit CLI Command.

Updated (V2.6.1)
- Fixed ImportError: Removed write_auto_ignored_reports (moved logic to Body).
- Fixed TypeError: Explicitly mapping AuditStats fields.
- Fully Compliant: CLI (Body) owns all side-effects (file writes).
- Restored: Always show findings grouped by rule; --verbose shows per-location detail.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from sqlalchemy import text

from body.services.file_service import FileService
from body.services.service_registry import service_registry
from cli.commands.check.converters import parse_min_severity
from cli.commands.check.formatters import (
    print_context_build_hints,
    print_summary_findings,
    print_verbose_findings,
)
from cli.logic.audit_renderer import AuditStats, render_overview
from cli.utils import core_command
from mind.governance.audit_postprocessor import apply_entry_point_downgrade
from mind.governance.audit_report_writer import build_auto_ignored_markdown
from mind.governance.auditor import ConstitutionalAuditor
from mind.governance.filtered_audit import run_filtered_audit
from shared.activity_logging import activity_run
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver

from .hub import app


console = Console()
logger = getLogger(__name__)


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
    files: list[str] = typer.Option(
        [],
        "--files",
        "-f",
        help=(
            "Scope per-file rules to these paths (repo-relative or "
            "absolute, repeatable). Context-level rules skip with a "
            "warning. Closes #279 — enables pre-commit-style focused audits."
        ),
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    classify: bool = typer.Option(
        False,
        "--classify",
        help="Print context build commands for all findings.",
    ),
    force_llm: bool = typer.Option(
        False,
        "--force-llm",
        help=(
            "Bypass the ADR-044 llm_gate verdict cache for this run. "
            "Every llm_gate rule re-evaluates every pre-selected file via "
            "Ollama; cache rows are still updated with fresh verdicts. "
            "Use after suspect cache state or to validate a model upgrade."
        ),
    ),
) -> None:
    """Run the constitutional self-audit."""
    min_severity = parse_min_severity(severity)
    core_context = ctx.obj
    repo_root = core_context.git_service.repo_path
    path_resolver = PathResolver.from_repo(repo_root)
    findings_file = str(
        (path_resolver.reports_dir / "audit_findings.json").relative_to(repo_root)
    )
    evidence_file = str(
        (path_resolver.reports_dir / "audit" / "latest_audit.json").relative_to(
            repo_root
        )
    )
    ignored_report_md = str(
        (path_resolver.reports_dir / "audit_auto_ignored.md").relative_to(repo_root)
    )
    ignored_report_json = str(
        (path_resolver.reports_dir / "audit_auto_ignored.json").relative_to(repo_root)
    )
    audit_subdir = str((path_resolver.reports_dir / "audit").relative_to(repo_root))
    file_service = FileService(repo_root)
    file_service.ensure_dir(audit_subdir)

    with activity_run("constitutional_audit") as run:
        async with service_registry.session() as session:
            core_context.auditor_context.db_session = session
            # ADR-044: plumb --force-llm onto the per-run context so the
            # rule_executor can thread it through to llm_gate.verify().
            core_context.auditor_context.force_llm = force_llm
            auditor = ConstitutionalAuditor(core_context.auditor_context)
            start_time = time.perf_counter()

            # ADR-279 / #279: --files alone (no --rule / --policy) is a
            # legitimate pre-commit-hook use case — run all rules, scope
            # to staged files. Routes through the filtered path so the
            # file_filter reaches execute_rule.
            if rule or policy or files:
                await core_context.auditor_context.load_knowledge_graph()
                raw_findings, executed_ids, stats_dict = await run_filtered_audit(
                    core_context.auditor_context,
                    rule_ids=rule,
                    policy_ids=policy,
                    files=files or None,
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

        # Compute verdict_str once — needed for both the Evidence Ledger
        # (conditional) and the Rich panel render (always). AuditVerdict
        # is a tri-state (PASS/FAIL/DEGRADED); fall back to PASS/FAIL only
        # when the auditor didn't supply a verdict (e.g. filtered runs).
        verdict = results.get("verdict")
        verdict_str = (
            verdict.value if verdict else ("PASS" if results["passed"] else "FAIL")
        )

        if not (rule or policy or files):
            # Full-audit artifacts only: filtered runs (--rule, --policy,
            # --files) are partial and must not overwrite findings.json,
            # the evidence ledger, or the audit_runs row that the
            # dashboard reads.
            # Write Main Findings
            file_service.write_file(
                findings_file, json.dumps(processed_findings, indent=2)
            )

            # Write Ignored Reports (Body uses Mind's string builder)
            md_content = build_auto_ignored_markdown(timestamp_str, ignored_data)
            file_service.write_file(ignored_report_md, md_content)
            file_service.write_runtime_json(
                ignored_report_json,
                {"generated_at": timestamp_str, "items": ignored_data},
            )

            # Record Evidence Ledger
            evidence = {
                "audit_id": run.run_id,
                "timestamp": timestamp_str,
                "passed": results["passed"],
                "findings_count": len(processed_findings),
                "executed_rules": sorted(list(results["executed_rule_ids"])),
                "verdict": verdict_str,
            }
            file_service.write_file(evidence_file, json.dumps(evidence, indent=2))

            # Persist run to core.audit_runs (best-effort; never aborts the
            # CLI on failure). Dashboard Panel 4 reads this table — without
            # the row it shows "never". Skipped for filtered runs (--rule /
            # --policy) since those are partial, not full audit runs.
            try:
                sha = core_context.git_service.get_current_commit()[:40]
            except Exception:
                sha = ""

            now_utc = datetime.now(UTC)
            audit_run_started_at = now_utc - timedelta(seconds=duration)
            audit_run_finished_at = now_utc

            try:
                async with service_registry.session() as audit_runs_session:
                    async with audit_runs_session.begin():
                        result = await audit_runs_session.execute(
                            text(
                                """
                                INSERT INTO core.audit_runs (
                                    source, commit_sha, score, passed,
                                    violations_found, started_at, finished_at
                                )
                                VALUES (
                                    :source, :sha, :score, :passed,
                                    :violations_found, :started_at, :finished_at
                                )
                                RETURNING id
                                """
                            ),
                            dict(
                                source="manual",
                                sha=sha,
                                score=None,
                                passed=results["passed"],
                                violations_found=len(processed_findings),
                                started_at=audit_run_started_at,
                                finished_at=audit_run_finished_at,
                            ),
                        )
                        audit_run_id = result.scalar_one()
                logger.debug(
                    "audit_command: persisted core.audit_runs row id=%s",
                    audit_run_id,
                )
            except Exception as exc:
                logger.warning(
                    "audit_command: failed to persist core.audit_runs row: %s",
                    exc,
                )

    # 3. Presentation
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
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    render_overview(
        console,
        all_findings,
        audit_stats,
        duration,
        results["passed"],
        verdict_str=verdict_str,
    )

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    if classify:
        print_context_build_hints(all_findings)

    if not results["passed"]:
        print_context_build_hints(all_findings)
        raise typer.Exit(1)
