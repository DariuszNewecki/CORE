# src/cli/resources/code/audit.py
"""Constitutional Audit CLI Command.

ADR-054 Phase 1: this CLI is a thin client over `POST /v1/audit/runs`
with `wait=true`. The server runs the audit, persists the
`core.audit_runs` row, and writes the report files; the CLI only
renders the result and sets the exit code.

Display-only options (`--severity`, `--verbose`, `--classify`) stay
client-side. Audit-shaping options (`--rule`, `--policy`, `--files`,
`--force-llm`) are forwarded to the server.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli.client import CoreApiClient
from cli.commands.check.converters import parse_min_severity
from cli.commands.check.formatters import (
    print_context_build_hints,
    print_summary_findings,
    print_verbose_findings,
)
from cli.logic.audit_renderer import AuditStats, render_overview, to_audit_finding
from cli.utils import core_command

from .hub import app


console = Console()
logger = logging.getLogger(__name__)


@app.command("audit")
@core_command(dangerous=False, requires_context=False)
# ID: 67107783-c506-4634-a23c-c118e86befa8
async def audit_command(
    ctx: typer.Context,
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
    """Run the constitutional self-audit (via /v1/audit/runs)."""
    min_severity = parse_min_severity(severity)

    client = CoreApiClient()
    result = await client.audit(
        rule_ids=list(rule),
        policy_ids=list(policy),
        files=list(files),
        force_llm=force_llm,
        source="manual",
    )

    raw_stats = result.get("stats", {}) or {}
    audit_stats = AuditStats(
        total_rules=raw_stats.get("total_executable_rules", 0),
        executed_rules=raw_stats.get("executed_dynamic_rules", 0),
        coverage_percent=raw_stats.get("coverage_percent", 0),
        total_declared_rules=raw_stats.get("total_declared_rules", 0),
        crashed_rules=raw_stats.get("crashed_rules", 0),
        unmapped_rules=raw_stats.get("unmapped_rules", 0),
        effective_coverage_percent=raw_stats.get("effective_coverage_percent", 0),
    )

    all_findings = [to_audit_finding(f) for f in result.get("findings", [])]
    filtered_findings = [f for f in all_findings if f.severity >= min_severity]

    render_overview(
        console,
        all_findings,
        audit_stats,
        result.get("duration_sec", 0.0),
        result["passed"],
        verdict_str=result["verdict"],
    )

    if filtered_findings:
        if verbose:
            print_verbose_findings(filtered_findings)
        else:
            print_summary_findings(filtered_findings)

    if classify:
        print_context_build_hints(all_findings)

    if not result["passed"]:
        print_context_build_hints(all_findings)
        raise typer.Exit(1)
