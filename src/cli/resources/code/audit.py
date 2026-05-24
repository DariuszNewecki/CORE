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
from body.services.coherence_service import CoherenceService
from body.services.representation_coherence_service import (
    RepresentationCoherenceService,
)
from cli.commands.check.converters import parse_min_severity
from cli.commands.check.formatters import (
    print_context_build_hints,
    print_summary_findings,
    print_verbose_findings,
)
from cli.logic.audit_renderer import AuditStats, render_overview, to_audit_finding
from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session

from .hub import app


console = Console()
logger = logging.getLogger(__name__)


@app.command("audit")
@core_command(dangerous=False, requires_context=False)
# ID: 67107783-c506-4634-a23c-c118e86befa8
async def audit_command(
    ctx: typer.Context,
    severity: str = typer.Option("high", "--severity", "-s"),
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

    # ADR-067 D5: append Constitutional Coherence advisory. Advisory only —
    # any CCC DB failure is logged and the line silently skipped so audit
    # semantics are not affected.
    try:
        async with get_session() as session:
            await _print_coherence_advisory(console, CoherenceService(session))
    except Exception as exc:
        logger.warning("CCC advisory line skipped: %s", exc)

    # ADR-070 D6: append Representation Coherence advisory. Advisory only —
    # any inventory load or DB failure is logged and the line silently
    # skipped so audit semantics are not affected.
    try:
        async with get_session() as session:
            await _print_representation_coherence_advisory(
                console, RepresentationCoherenceService(session)
            )
    except Exception as exc:
        logger.warning("Representation Coherence advisory line skipped: %s", exc)

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


async def _print_coherence_advisory(
    console: Console, coherence_service: CoherenceService
) -> None:
    """ADR-067 D5: print one Constitutional Coherence advisory line.

    Three cases:
      - no runs:    Constitutional Coherence: no runs recorded — run
                    `core-admin coherence check --full`
      - open runs:  Constitutional Coherence: {N} open run(s) ·
                    {M} candidate(s) unreviewed
      - all closed: Constitutional Coherence: clean (last run {YYYY-MM-DD})
    """
    summary = await coherence_service.get_unreviewed_summary()
    latest = await coherence_service.get_latest_run()

    if latest is None:
        console.print(
            "Constitutional Coherence: no runs recorded — run "
            "`core-admin coherence check --full`"
        )
        return

    if summary["open_runs"] > 0:
        console.print(
            f"Constitutional Coherence: {summary['open_runs']} open run(s) "
            f"· {summary['unreviewed']} candidate(s) unreviewed"
        )
        return

    run_date = latest["run_at"].date().isoformat()
    console.print(f"Constitutional Coherence: clean (last run {run_date})")


async def _print_representation_coherence_advisory(
    console: Console, service: RepresentationCoherenceService
) -> None:
    """ADR-070 D6: print one Representation Coherence advisory line.

    Four cases:
      - inventory missing: Representation Coherence: no inventory file
                           — see .intent/governance/projections.yaml
      - empty inventory:   Representation Coherence: no pairs declared
                           — see .intent/governance/projections.yaml
      - all in-lease:      Representation Coherence: clean
                           ({N} pair(s) · last check {YYYY-MM-DD HH:MM:SSZ})
      - mixed state:       Representation Coherence:
                           {A} in-lease · {B} drifted · {C} sensor-stale
    """
    summary = await service.get_summary()

    if not summary["inventory_loaded"]:
        console.print(
            "Representation Coherence: no inventory file "
            "— see .intent/governance/projections.yaml"
        )
        return

    if summary["pairs_declared"] == 0:
        console.print(
            "Representation Coherence: no pairs declared "
            "— see .intent/governance/projections.yaml"
        )
        return

    if summary["drifted"] == 0 and summary["sensor_stale"] == 0:
        last_check = summary["last_check_at"]
        if last_check is not None:
            ts = last_check.strftime("%Y-%m-%d %H:%M:%SZ")
            console.print(
                f"Representation Coherence: clean "
                f"({summary['pairs_declared']} pair(s) · last check {ts})"
            )
        else:
            console.print(
                f"Representation Coherence: clean ({summary['pairs_declared']} pair(s))"
            )
        return

    console.print(
        f"Representation Coherence: {summary['in_lease']} in-lease "
        f"· {summary['drifted']} drifted "
        f"· {summary['sensor_stale']} sensor-stale"
    )
