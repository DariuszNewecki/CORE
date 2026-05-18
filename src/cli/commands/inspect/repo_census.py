# src/cli/commands/inspect/repo_census.py
"""
CIM-0: Repository Structural Census command.

Thin client over /v1/census/* (ADR-058 D1). The API runs `CensusService`,
`BaselineManager`, and `DiffEngine` server-side; the CLI dispatches,
polls the async run, and renders the result payload.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()


@core_command(dangerous=False, requires_context=False)
# ID: 57d975ad-ad77-453a-a7c4-9779eaa9e542
async def repo_census_cmd(
    ctx: typer.Context,
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Repository root to inspect (server-side: API resolves repo root).",
    ),
    out: Path = typer.Option(
        None, "--out", "-o", help="Ignored — output paths are server-managed."
    ),
    snapshot: bool = typer.Option(
        False, "--snapshot", help="Save census as immutable snapshot"
    ),
    set_baseline: str = typer.Option(
        None, "--set-baseline", help="Create named baseline from this census"
    ),
    list_baselines_flag: bool = typer.Option(
        False, "--list-baselines", help="List all baselines"
    ),
    diff_baseline: str = typer.Option(
        None, "--diff", help="Compare against named baseline"
    ),
    diff_prev: bool = typer.Option(
        False, "--diff-prev", help="Compare against previous snapshot"
    ),
) -> None:
    """CIM-0: Perform a mechanical census of the repository.

    Modes:
    - Default: Run census via POST /v1/census/runs
    - --snapshot: Persist as immutable snapshot server-side
    - --set-baseline NAME: Create named baseline (requires --snapshot)
    - --list-baselines: GET /v1/census/baselines
    - --diff NAME: GET /v1/census/diff?baseline=NAME
    - --diff-prev: GET /v1/census/diff (no baseline)
    """
    _ = ctx
    _ = path  # API resolves repo_root server-side; --path retained for compatibility.
    _ = out  # SUPPRESS architecture.cli.api_only: output paths are now server-
    # managed; the --out flag is kept for backward compatibility but ignored.
    client = CoreApiClient()

    if list_baselines_flag:
        payload = await client.census_list_baselines()
        _render_baseline_list(payload)
        return

    console.print("[blue]Running CIM-0 census via /v1/census/runs[/blue]")
    initial = await client.census_run(snapshot=snapshot)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]Error: census dispatch failed: {initial}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Dispatched run {run_id} — polling…[/dim]")
    final = await client.poll_census_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]Census failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)

    result = final.get("result") or {}
    tree = result.get("tree") or {}
    console.print("[green]✓ Census complete[/green]")
    console.print(f"  Files scanned: {tree.get('total_files', '?')}")
    console.print(
        f"  Execution surfaces: {len(result.get('execution_surfaces') or [])}"
    )
    console.print(f"  Mutation surfaces: {len(result.get('mutation_surfaces') or [])}")
    snapshot_file = result.get("snapshot_file")
    if snapshot and snapshot_file:
        console.print(f"[green]✓ Snapshot saved: {snapshot_file}[/green]")

    if set_baseline:
        if not snapshot:
            console.print(
                "[yellow]Warning: --set-baseline requires --snapshot[/yellow]"
            )
        else:
            baseline_payload = await client.census_create_baseline(
                name=set_baseline, snapshot_file=snapshot_file
            )
            console.print(f"[green]✓ Baseline '{set_baseline}' created[/green]")
            _ = baseline_payload

    if diff_baseline or diff_prev:
        baseline_name = diff_baseline if diff_baseline else None
        diff_payload = await client.census_diff(baseline=baseline_name)
        if not diff_payload.get("available", True):
            err = diff_payload.get("error", "diff unavailable")
            console.print(f"[yellow]{err}[/yellow]")
            raise typer.Exit(0)
        _display_diff(diff_payload)
        # ADR-058 does not currently expose a policy-evaluation exit code
        # via /v1/census/diff. Exit 0 on successful diff render; policy
        # evaluation moves server-side in a future iteration.
        raise typer.Exit(0)


def _render_baseline_list(payload: dict) -> None:
    """Render the baseline list returned by /v1/census/baselines."""
    baselines = payload.get("baselines") or []
    if not baselines:
        console.print("[yellow]No baselines found[/yellow]")
        return
    table = Table(title="CIM Baselines")
    table.add_column("Name", style="cyan")
    table.add_column("Snapshot", style="white")
    table.add_column("Commit", style="dim")
    table.add_column("Created", style="green")
    for baseline in baselines:
        commit = (baseline.get("git_commit") or "")[:8] or "—"
        created_raw = baseline.get("created_at", "")
        created = str(created_raw)[:16] if created_raw else "—"
        table.add_row(
            str(baseline.get("name", "")),
            str(baseline.get("snapshot_file", "")),
            commit,
            created,
        )
    console.print(table)


def _display_diff(diff_payload: dict) -> None:
    """Render a /v1/census/diff payload in human-readable form."""
    diff = diff_payload.get("diff") or {}
    baseline_name = (
        diff_payload.get("baseline") or diff.get("baseline_name") or "previous"
    )
    console.print()
    console.print("[bold]Census Diff Summary[/bold]")
    console.print(f"Baseline: {baseline_name}")
    console.print()

    exec_delta = (diff.get("execution_surfaces") or {}).get("delta", "—")
    mut_total_delta = (diff.get("mutation_surfaces_total") or {}).get("delta", "—")
    write_ephemeral_delta = (diff.get("write_ephemeral") or {}).get("delta", "—")
    write_production_delta = (diff.get("write_production") or {}).get("delta", "—")
    console.print(f"Execution surfaces: {exec_delta}")
    console.print(f"Mutation surfaces: {mut_total_delta}")
    console.print(f"  Ephemeral writes: {write_ephemeral_delta}")
    console.print(f"  Production writes: {write_production_delta}")

    new_prohibited = diff.get("new_prohibited_writes", 0) or 0
    if new_prohibited > 0:
        console.print(f"  [red bold]Prohibited writes: +{new_prohibited}[/red bold]")

    console.print()
