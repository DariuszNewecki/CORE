# src/body/cli/commands/inspect/repo_census.py
# ID: 8ae646c0-1f4c-48f1-8cc1-d0cd8907c459

"""
CIM-0: Repository Structural Census command.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from body.services.cim import CensusService
from body.services.cim.baselines import BaselineManager
from body.services.cim.diff import DiffEngine
from body.services.cim.history import CensusHistory
from body.services.cim.policy import PolicyEvaluator
from shared.cli_utils import core_command
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 9a2cc7aa-6444-486d-8efd-ef97172b80c2
def repo_census_cmd(
    ctx: typer.Context,
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root to inspect (default: current CORE repo)",
    ),
    out: Path = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory (default: var/cim/)",
    ),
    snapshot: bool = typer.Option(
        False,
        "--snapshot",
        help="Save census as immutable snapshot",
    ),
    set_baseline: str = typer.Option(
        None,
        "--set-baseline",
        help="Create named baseline from this census",
    ),
    list_baselines: bool = typer.Option(
        False,
        "--list-baselines",
        help="List all baselines",
    ),
    diff_baseline: str = typer.Option(
        None,
        "--diff",
        help="Compare against named baseline",
    ),
    diff_prev: bool = typer.Option(
        False,
        "--diff-prev",
        help="Compare against previous snapshot",
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
    # Default paths
    if path is None:
        path = settings.REPO_PATH
    else:
        path = path.resolve()

    if not path.exists():
        console.print(f"[red]Error: Path does not exist: {path}[/red]")
        raise typer.Exit(1)

    if not path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {path}[/red]")
        raise typer.Exit(1)

    if out is None:
        out = settings.REPO_PATH / "var" / "cim"

    out.mkdir(parents=True, exist_ok=True)

    # Initialize services
    history = CensusHistory(out / "history")
    baselines = BaselineManager(out / "baselines.json")
    diff_engine = DiffEngine()
    policy_eval = PolicyEvaluator(
        settings.REPO_PATH / ".intent" / "cim" / "thresholds.yaml"
    )

    # Handle --list-baselines
    if list_baselines:
        _list_baselines(baselines)
        return

    # Run census
    console.print(f"[blue]Running CIM-0 census on: {path}[/blue]")
    service = CensusService()
    census = service.run_census(path)

    # Save as latest
    latest_file = out / "repo_census.json"
    with latest_file.open("w", encoding="utf-8") as f:
        json.dump(census.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    console.print(f"[green]✓ Census complete: {latest_file}[/green]")
    console.print(f"  Files scanned: {census.tree.total_files}")
    console.print(f"  Execution surfaces: {len(census.execution_surfaces)}")
    console.print(f"  Mutation surfaces: {len(census.mutation_surfaces)}")

    # Handle --snapshot
    if snapshot:
        snapshot_path = history.save_snapshot(census)
        console.print(f"[green]✓ Snapshot saved: {snapshot_path}[/green]")

    # Handle --set-baseline
    if set_baseline:
        if not snapshot:
            console.print(
                "[yellow]Warning: --set-baseline requires --snapshot[/yellow]"
            )
        else:
            baseline = baselines.set_baseline(
                set_baseline,
                snapshot_path.name,
                census.repo.git_commit,
            )
            console.print(f"[green]✓ Baseline '{set_baseline}' created[/green]")

    # Handle --diff
    if diff_baseline or diff_prev:
        baseline_census = None
        baseline_name = None

        if diff_baseline:
            baseline_ref = baselines.get_baseline(diff_baseline)
            if not baseline_ref:
                console.print(f"[red]Error: Baseline '{diff_baseline}' not found[/red]")
                raise typer.Exit(1)
            baseline_census = history.load_snapshot(baseline_ref.snapshot_file)
            baseline_name = diff_baseline
        else:  # diff_prev
            baseline_census = history.get_previous_snapshot()
            if not baseline_census:
                console.print("[yellow]No previous snapshot found[/yellow]")
                raise typer.Exit(0)
            baseline_name = "previous"

        # Compute diff
        diff = diff_engine.compute_diff(baseline_census, census, baseline_name)

        # Evaluate policy
        evaluation = policy_eval.evaluate(diff)

        # Save diff report
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

        # Display results
        _display_diff(diff, evaluation)

        raise typer.Exit(evaluation.exit_code)


def _list_baselines(baselines: BaselineManager):
    """Display all baselines."""
    baseline_list = baselines.list_baselines()

    if not baseline_list:
        console.print("[yellow]No baselines found[/yellow]")
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

    console.print(table)


def _display_diff(diff, evaluation):
    """Display diff and findings in human-readable format."""
    console.print()
    console.print("[bold]Census Diff Summary[/bold]")
    console.print(f"Baseline: {diff.baseline_name or 'previous'}")
    console.print()

    # Key metrics
    console.print(f"Execution surfaces: {diff.execution_surfaces.delta:+d}")
    console.print(f"Mutation surfaces: {diff.mutation_surfaces_total.delta:+d}")
    console.print(f"  Ephemeral writes: {diff.write_ephemeral.delta:+d}")
    console.print(f"  Production writes: {diff.write_production.delta:+d}")

    if diff.new_prohibited_writes > 0:
        console.print(
            f"  [red bold]Prohibited writes: +{diff.new_prohibited_writes}[/red bold]"
        )

    # Findings
    if evaluation.findings:
        console.print()
        console.print("[bold]Policy Findings:[/bold]")

        for finding in evaluation.findings:
            severity_color = {
                "BLOCK": "red bold",
                "HIGH": "red",
                "MEDIUM": "yellow",
                "LOW": "cyan",
                "INFO": "white",
            }[finding.severity]

            console.print(
                f"  [{severity_color}]{finding.severity}[/{severity_color}] {finding.evidence}"
            )
            console.print(f"    → {finding.recommendation}")

    console.print()
    console.print(
        f"Exit code: {evaluation.exit_code} "
        f"(BLOCK: {evaluation.blocking_count}, "
        f"HIGH: {evaluation.high_count}, "
        f"MEDIUM: {evaluation.medium_count}, "
        f"LOW: {evaluation.low_count})"
    )
