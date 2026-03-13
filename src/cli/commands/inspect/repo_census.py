# src/cli/commands/inspect/repo_census.py
"""
CIM-0: Repository Structural Census command.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from body.services.cim import CensusService
from body.services.cim.baselines import BaselineManager
from body.services.cim.diff import DiffEngine
from body.services.cim.history import CensusHistory
from body.services.cim.policy import PolicyEvaluator
from shared.cli_utils import core_command
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext
logger = getLogger(__name__)
console = Console()


@core_command(dangerous=False, requires_context=True)
# ID: 57d975ad-ad77-453a-a7c4-9779eaa9e542
def repo_census_cmd(
    ctx: typer.Context,
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root to inspect (default: current CORE repo)",
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Output directory (default: var/cim/)"
    ),
    snapshot: bool = typer.Option(
        False, "--snapshot", help="Save census as immutable snapshot"
    ),
    set_baseline: str = typer.Option(
        None, "--set-baseline", help="Create named baseline from this census"
    ),
    list_baselines: bool = typer.Option(
        False, "--list-baselines", help="List all baselines"
    ),
    diff_baseline: str = typer.Option(
        None, "--diff", help="Compare against named baseline"
    ),
    diff_prev: bool = typer.Option(
        False, "--diff-prev", help="Compare against previous snapshot"
    ),
) -> None:
    """
    CIM-0: Perform a mechanical census of a repository.

    Modes:
    - Default: Run census and save to var/cim/repo_census.json
    - --snapshot: Save as immutable snapshot in var/cim/history/
    - --set-baseline NAME: Create named baseline
    - --list-baselines: Show all baselines
    - --diff NAME: Compare against baseline
    - --diff-prev: Compare against previous snapshot
    """
    context: CoreContext = ctx.obj
    if path is None:
        path = context.git_service.repo_path
    else:
        path = path.resolve()
    if not path.exists():
        logger.info("[red]Error: Path does not exist: %s[/red]", path)
        raise typer.Exit(1)
    if not path.is_dir():
        logger.info("[red]Error: Path is not a directory: %s[/red]", path)
        raise typer.Exit(1)
    if out is None:
        out = context.git_service.repo_path / "var" / "cim"
    out.mkdir(parents=True, exist_ok=True)
    history = CensusHistory(out / "history")
    baselines = BaselineManager(out / "baselines.json")
    diff_engine = DiffEngine()
    policy_eval = PolicyEvaluator(
        context.git_service.repo_path / ".intent" / "cim" / "thresholds.yaml"
    )
    if list_baselines:
        _list_baselines(baselines)
        return
    logger.info("[blue]Running CIM-0 census on: %s[/blue]", path)
    service = CensusService()
    census = service.run_census(path)
    latest_file = out / "repo_census.json"
    with latest_file.open("w", encoding="utf-8") as f:
        json.dump(census.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    logger.info("[green]✓ Census complete: %s[/green]", latest_file)
    logger.info("  Files scanned: %s", census.tree.total_files)
    logger.info("  Execution surfaces: %s", len(census.execution_surfaces))
    logger.info("  Mutation surfaces: %s", len(census.mutation_surfaces))
    if snapshot:
        snapshot_path = history.save_snapshot(census)
        logger.info("[green]✓ Snapshot saved: %s[/green]", snapshot_path)
    if set_baseline:
        if not snapshot:
            logger.info("[yellow]Warning: --set-baseline requires --snapshot[/yellow]")
        else:
            baseline = baselines.set_baseline(
                set_baseline, snapshot_path.name, census.repo.git_commit
            )
            logger.info("[green]✓ Baseline '%s' created[/green]", set_baseline)
    if diff_baseline or diff_prev:
        baseline_census = None
        baseline_name = None
        if diff_baseline:
            baseline_ref = baselines.get_baseline(diff_baseline)
            if not baseline_ref:
                logger.info("[red]Error: Baseline '%s' not found[/red]", diff_baseline)
                raise typer.Exit(1)
            baseline_census = history.load_snapshot(baseline_ref.snapshot_file)
            baseline_name = diff_baseline
        else:
            baseline_census = history.get_previous_snapshot()
            if not baseline_census:
                logger.info("[yellow]No previous snapshot found[/yellow]")
                raise typer.Exit(0)
            baseline_name = "previous"
        diff = diff_engine.compute_diff(baseline_census, census, baseline_name)
        evaluation = policy_eval.evaluate(diff)
        diff_report_path = out / "reports" / "cim_diff_latest.json"
        diff_report_path.parent.mkdir(parents=True, exist_ok=True)
        with diff_report_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "diff": diff.model_dump(mode="json"),
                    "evaluation": evaluation.model_dump(mode="json"),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        _display_diff(diff, evaluation)
        raise typer.Exit(evaluation.exit_code)


def _list_baselines(baselines: BaselineManager):
    """Display all baselines."""
    baseline_list = baselines.list_baselines()
    if not baseline_list:
        logger.info("[yellow]No baselines found[/yellow]")
        return
    table = Table(title="CIM Baselines")
    table.add_column("Name", style="cyan")
    table.add_column("Snapshot", style="white")
    table.add_column("Commit", style="dim")
    table.add_column("Created", style="green")
    for baseline in baseline_list:
        commit = baseline.git_commit[:8] if baseline.git_commit else "—"
        created = baseline.created_at.strftime("%Y-%m-%d %H:%M")
        table.add_row(baseline.name, baseline.snapshot_file, commit, created)
    logger.info(table)


def _display_diff(diff, evaluation):
    """Display diff and findings in human-readable format."""
    console.print()
    logger.info("[bold]Census Diff Summary[/bold]")
    logger.info("Baseline: %s", diff.baseline_name or "previous")
    console.print()
    logger.info("Execution surfaces: %s", diff.execution_surfaces.delta)
    logger.info("Mutation surfaces: %s", diff.mutation_surfaces_total.delta)
    logger.info("  Ephemeral writes: %s", diff.write_ephemeral.delta)
    logger.info("  Production writes: %s", diff.write_production.delta)
    if diff.new_prohibited_writes > 0:
        logger.info(
            "  [red bold]Prohibited writes: +%s[/red bold]", diff.new_prohibited_writes
        )
    if evaluation.findings:
        logger.info()
        logger.info("[bold]Policy Findings:[/bold]")
        for finding in evaluation.findings:
            severity_color = {
                "BLOCK": "red bold",
                "HIGH": "red",
                "MEDIUM": "yellow",
                "LOW": "cyan",
                "INFO": "white",
            }[finding.severity]
            logger.info(
                "  [%s]%s[/%s] %s",
                severity_color,
                finding.severity,
                severity_color,
                finding.evidence,
            )
            logger.info("    → %s", finding.recommendation)
    console.print()
    logger.info(
        "Exit code: %s (BLOCK: %s, HIGH: %s, MEDIUM: %s, LOW: %s)",
        evaluation.exit_code,
        evaluation.blocking_count,
        evaluation.high_count,
        evaluation.medium_count,
        evaluation.low_count,
    )
