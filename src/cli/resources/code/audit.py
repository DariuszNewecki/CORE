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

import json
import logging
import sys

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
from cli.utils.annotation_formatter import format_payload as format_github_payload
from cli.utils.codeclimate_formatter import format_payload as format_codeclimate_payload
from cli.utils.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_FINDINGS,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
)
from mind.governance.stateless_audit import run_stateless_audit
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.models import AuditSeverity
from shared.path_utils import get_repo_root

from .hub import app


console = Console()
logger = logging.getLogger(__name__)


@app.command("audit")
@core_command(dangerous=False, requires_context=False, offline_capable=True)
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
    offline: bool = typer.Option(
        False,
        "--offline",
        help=(
            "F-10.1b: run the constitutional audit without core-api / "
            "core-daemon / Postgres / Qdrant. Used by the F-10 CI/CD gate "
            "and the F-10.5 pre-commit hook. Rules requiring the knowledge "
            "graph or LLM (knowledge_gate, llm_gate) are skipped with a "
            "structured reason and surfaced in skipped_rules. See "
            "ADR-085 §D5 for the F-10 exit criterion this serves."
        ),
    ),
    target: str | None = typer.Option(
        None,
        "--target",
        help=(
            "#688: path to an external repo to audit. Requires --offline. "
            "The repo must have a .intent/ directory (produced by "
            "`core-admin project onboard`). When omitted, the audit runs "
            "against the repo found by walking up from the current directory."
        ),
    ),
    output_format: str = typer.Option(
        "text",
        "--format",
        help=(
            "F-10.1b / F-10.2: output format. `text` (default) renders "
            "the human-readable Rich output. `json` emits the F-10.1a "
            "payload verbatim on stdout (schema documented in #535). "
            "`github-annotations` emits GitHub Actions workflow-command "
            "lines so findings surface inline in PR diff view "
            "(#529 / F-10.2). `codeclimate` emits CodeClimate JSON for "
            "GitLab MR quality reports via `artifacts: reports: codequality:` "
            "(F-10.P2). Non-text formats require --offline; the "
            "daemon-driven path has a different result shape."
        ),
    ),
) -> None:
    """Run the constitutional self-audit.

    Default mode: HTTP client over /v1/audit/runs (requires core-api).
    With --offline: stateless invocation without daemon/DB (F-10 CI gate).
    """
    min_severity = parse_min_severity(severity)

    if output_format not in {"text", "json", "github-annotations", "codeclimate"}:
        console.print(
            f"[bold red]--format must be one of "
            f"text|json|github-annotations|codeclimate[/bold red] (got {output_format!r})"
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)

    if output_format not in {"text"} and not offline:
        console.print(
            f"[bold red]--format={output_format} currently requires "
            f"--offline[/bold red] (daemon-driven path has a different "
            "result shape; see #535)"
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)

    if target is not None and not offline:
        console.print(
            "[bold red]--target requires --offline[/bold red] "
            "(the daemon-driven path cannot be directed at an external repo)"
        )
        raise typer.Exit(EXIT_CONFIG_ERROR)

    if offline:
        await _run_offline_audit(
            files=list(files),
            min_severity_str=severity,
            output_format=output_format,
            target=target,
        )
        return

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
        # ADR-076 D4
        context_level_rules=raw_stats.get("context_level_rules", 0),
        per_file_rules=raw_stats.get("per_file_rules", 0),
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
        raise typer.Exit(EXIT_FINDINGS)


# ID: aca519c8-5fe1-4f11-ac45-fbaa937c981b
async def _run_offline_audit(
    *,
    files: list[str],
    min_severity_str: str,
    output_format: str,
    target: str | None = None,
) -> None:
    """F-10.1b / F-10.2 — execute the stateless audit + render per format.

    Routes to mind.governance.stateless_audit (F-10.1a). Exit code matrix:

    - EXIT_OK (0)             : no findings >= severity floor
    - EXIT_FINDINGS (1)       : N findings >= severity floor; merge-block
    - EXIT_CONFIG_ERROR (2)   : .intent/ unreachable, IntentRepository fails,
                                or governance collapse (ADR-108 D4 — rules
                                declared but none map to an enforceable engine)
    - EXIT_INTERNAL_ERROR (64): caught here as the top-level guard

    Per ADR-085 §D5, exit code 1 vs 64 is constitutionally meaningful for
    the merge-block path: 1 = "your code has violations" (developer action);
    64 = "the gate itself crashed" (operator action). External CI branch
    protection rules should treat them differently.

    output_format dispatches the rendering: ``text`` -> Rich console
    (default for humans); ``json`` -> F-10.1a payload verbatim (CLI
    integrations); ``github-annotations`` -> GH workflow-command lines
    (F-10.3 Action, F-10.5 pre-commit hook).

    target: when set, audits the given directory instead of the cwd-derived
    repo (#688). Must be a path containing a .intent/ tree.
    """
    structured = output_format in {"json", "github-annotations", "codeclimate"}

    try:
        if target is not None:
            from pathlib import Path as _Path

            target_path = _Path(target).resolve()
            repo_path = get_repo_root(start_dir=target_path)
            intent_repo = IntentRepository(strict=True, root=repo_path / ".intent")
            intent_repo.initialize()
        else:
            intent_repo = get_intent_repository()
            repo_path = get_repo_root()
    except Exception as exc:
        _emit_error(output_format, "configuration error", exc)
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc

    min_severity = parse_min_severity(min_severity_str)

    try:
        result = await run_stateless_audit(
            intent_repo=intent_repo,
            repo_path=repo_path,
            files=files or None,
        )
    except Exception as exc:
        logger.exception("Stateless audit crashed")
        _emit_error(output_format, "internal error", exc)
        raise typer.Exit(EXIT_INTERNAL_ERROR) from exc

    # ADR-108 D4: governance collapse fails closed with a distinct ERROR
    # verdict (the gate could enforce nothing). This is operator action
    # (exit 2), not developer action (exit 1) — the constitution declared
    # rules but none mapped to an engine.
    if result.get("verdict") == "ERROR":
        msg = result.get("error", "audit could not enforce any declared rule")
        if output_format == "json":
            sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
        elif output_format == "github-annotations":
            safe = str(msg).replace("%", "%25").replace("\n", "%0A")
            sys.stdout.write(f"::error title=CORE audit governance error::{safe}\n")
        elif output_format == "codeclimate":
            # Emit a synthetic CodeClimate issue so the MR quality tab shows the error.
            error_issue = [
                {
                    "type": "issue",
                    "check_name": "core.audit.governance_error",
                    "description": f"[blocking] CORE audit governance error: {msg}",
                    "categories": ["Bug Risk"],
                    "location": {"path": ".", "lines": {"begin": 1}},
                    "severity": "blocker",
                    "fingerprint": "core-audit-governance-error",
                }
            ]
            sys.stdout.write(json.dumps(error_issue, indent=2) + "\n")
        else:
            console.print(f"[bold red]Governance error:[/bold red] {msg}")
        raise typer.Exit(EXIT_CONFIG_ERROR)

    blocking_findings = [
        f for f in result["findings"] if to_audit_finding(f).severity >= min_severity
    ]

    if output_format == "json":
        sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    elif output_format == "github-annotations":
        sys.stdout.write(format_github_payload(result))
    elif output_format == "codeclimate":
        sys.stdout.write(format_codeclimate_payload(result))
    else:
        _render_text_summary(result, min_severity)

    raise typer.Exit(EXIT_FINDINGS if blocking_findings else EXIT_OK)


# ID: 4d8287ab-678e-4fb9-bcf5-05eab155ace1
def _emit_error(output_format: str, kind: str, exc: Exception) -> None:
    """Emit an error payload in the active format (CI parsers vs humans)."""
    if output_format == "json":
        sys.stdout.write(
            json.dumps(
                {
                    "verdict": "ERROR",
                    "passed": False,
                    "error": f"{kind}: {exc!s}",
                    "mode": "stateless",
                }
            )
            + "\n"
        )
    elif output_format == "github-annotations":
        msg = f"{kind}: {exc!s}".replace("%", "%25").replace("\n", "%0A")
        sys.stdout.write(f"::error title=CORE audit {kind}::{msg}\n")
    elif output_format == "codeclimate":
        error_issue = [
            {
                "type": "issue",
                "check_name": f"core.audit.{kind.replace(' ', '_')}",
                "description": f"[blocking] CORE audit {kind}: {exc!s}",
                "categories": ["Bug Risk"],
                "location": {"path": ".", "lines": {"begin": 1}},
                "severity": "blocker",
                "fingerprint": f"core-audit-{kind.replace(' ', '-')}",
            }
        ]
        sys.stdout.write(json.dumps(error_issue, indent=2) + "\n")
    else:
        console.print(f"[bold red]{kind.capitalize()}:[/bold red] {exc}")


# ID: c70adf31-b238-466d-9e78-f1461e437f67
def _render_text_summary(result: dict, min_severity: AuditSeverity) -> None:
    """Human-readable Rich rendering for the offline path."""
    all_findings = [to_audit_finding(f) for f in result["findings"]]
    stats = result.get("stats", {})
    audit_stats = AuditStats(
        total_rules=stats.get("total_rules", 0),
        executed_rules=stats.get("runnable_rules", 0),
        coverage_percent=0,
        total_declared_rules=stats.get("total_rules", 0),
        crashed_rules=0,
        unmapped_rules=0,
        effective_coverage_percent=0,
        context_level_rules=0,
        per_file_rules=0,
    )
    render_overview(
        console,
        all_findings,
        audit_stats,
        result.get("duration_sec", 0.0),
        result["passed"],
        verdict_str=result["verdict"],
    )
    skipped = result.get("skipped_rules", [])
    if skipped:
        console.print(
            f"[dim]Skipped {len(skipped)} rule(s) in stateless mode "
            f"(knowledge_gate + llm_gate require DB); pass "
            f"--format=json to see structured reasons.[/dim]"
        )
    filtered = [f for f in all_findings if f.severity >= min_severity]
    if filtered:
        print_summary_findings(filtered)


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
