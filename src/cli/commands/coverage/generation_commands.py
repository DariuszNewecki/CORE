# src/cli/commands/coverage/generation_commands.py
"""Test generation commands — V2 adaptive architecture.

Thin clients over POST /v1/coverage/generate and /v1/coverage/generate:batch
(ADR-057 D1). The async resource lifecycle (pending → executing →
completed/failed) is polled via CoreApiClient.poll_coverage_run; the
server owns the file iteration and the adaptive generator instance.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command


logger = logging.getLogger(__name__)
console = Console()


# ID: b27c8ef7-9e92-4995-ae21-3a2f7d42b73d
def register_generation_commands(app: typer.Typer) -> None:
    """Register V2 test generation commands."""
    app.command("generate-adaptive")(generate_adaptive_command)
    app.command("generate-adaptive-batch")(generate_adaptive_batch_command)


@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: 35d81f3f-de8f-4984-b9ab-0b311669268d
async def generate_adaptive_command(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="Source file to generate tests for"),
    write: bool = typer.Option(
        False,
        "--write",
        help=(
            "Required — the legacy adaptive generator has no dry-run mode "
            "and writes test files unconditionally. Must be passed "
            "explicitly; omitting it exits without calling the API (#809)."
        ),
    ),
    max_failures: int = typer.Option(
        3, "--max-failures", help="Switch strategy after N failures with same pattern"
    ),
) -> None:
    """Generate tests using adaptive learning (V2 - Component Architecture)."""
    _ = ctx
    _ = max_failures  # The API owns the adaptive failure threshold.
    if not write:
        console.print(
            "[red]This legacy generation command currently writes test "
            "files unconditionally — there is no dry-run mode. Re-run with "
            "--write to confirm mutation.[/red]"
        )
        raise typer.Exit(code=2)
    console.print("[bold cyan]🧪 Adaptive Test Generation (V2)[/bold cyan]\n")

    client = CoreApiClient()
    initial = await client.coverage_generate(target_file=file_path, write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]❌ coverage_generate failed to dispatch: {initial}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[dim]Dispatched run {run_id} — polling…[/dim]")
    final = await client.poll_coverage_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]❌ Generation failed: {final.get('error') or final}[/red]")
        raise typer.Exit(code=1)

    # EnhancedSingleFileRemediationService.remediate()'s real success shape:
    # {"status": "completed", "file", "test_file", "final_coverage", "metrics"}.
    # The key list this used to render (sandbox_passed, patterns_learned,
    # strategy_switches, ...) never existed in that shape — this rendered
    # near-empty on every run, success or not (#813).
    payload = final.get("result") or {}
    console.print("\n[bold]📊 Generation Results:[/bold]")
    console.print(f"  File: {payload.get('file', file_path)}")
    console.print(f"  Test file: {payload.get('test_file', 'unknown')}")
    final_coverage = payload.get("final_coverage")
    if final_coverage is not None:
        console.print(f"  Final coverage: {final_coverage}%")

    console.print("\n[dim]Write mode:[/dim]")
    console.print("  • Passing tests -> tests/... (mirrored)")
    console.print("  • Failing tests  -> var/artifacts/test_gen/failures/...")

    # final["status"] == "completed" was already confirmed above (coverage_runs
    # row status now correctly reflects the generator's own "completed" status
    # per #813's coverage_runner.py fix) — reaching here always means success.
    console.print("\n[bold green]✅ Completed generation cycle.[/bold green]")


@core_command(dangerous=True, confirmation=True, requires_context=False)
# ID: 4158a9ca-f87e-4311-8a02-ea8d5e696f40
async def generate_adaptive_batch_command(
    ctx: typer.Context,
    priority: str = typer.Option(
        "all", "--priority", help="Batch priority: 'high' or 'all'."
    ),
    write: bool = typer.Option(
        False,
        "--write",
        help=(
            "Required — the legacy adaptive generator has no dry-run mode "
            "and writes test files unconditionally. Must be passed "
            "explicitly; omitting it exits without calling the API (#809)."
        ),
    ),
) -> None:
    """Generate tests for multiple files via the API batch endpoint."""
    _ = ctx
    if priority not in {"high", "all"}:
        console.print(
            f"[red]Unknown priority '{priority}'. Allowed: 'high', 'all'.[/red]"
        )
        raise typer.Exit(code=1)
    if not write:
        console.print(
            "[red]This legacy generation command currently writes test "
            "files unconditionally — there is no dry-run mode. Re-run with "
            "--write to confirm mutation.[/red]"
        )
        raise typer.Exit(code=2)

    console.print(
        "[bold cyan]🧪 Adaptive Test Generation - Batch Mode (V2)[/bold cyan]\n"
    )
    console.print(f"[cyan]Priority: {priority}[/cyan]")
    console.print("[dim]Write mode: on[/dim]\n")

    client = CoreApiClient()
    initial = await client.coverage_generate_batch(priority=priority, write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(
            f"[red]❌ coverage_generate_batch failed to dispatch: {initial}[/red]"
        )
        raise typer.Exit(code=1)

    console.print(f"[dim]Dispatched run {run_id} — polling…[/dim]")
    final = await client.poll_coverage_run(run_id, timeout_seconds=1800.0)
    if final.get("status") != "completed":
        console.print(
            f"[red]❌ Batch generation failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(code=1)

    # BatchRemediationService.process_batch()'s real shape: {"status",
    # "processed", "results": [...], "summary": {"success","failed","skipped"}}.
    # The key list this used to render (files_processed, tests_sandbox_passed,
    # tests_saved, ...) never existed — rendered near-empty every run (#813).
    payload = final.get("result") or {}
    summary = payload.get("summary") or {}
    console.print("\n" + "=" * 80)
    console.print("[bold]📊 Batch Generation Summary[/bold]\n")
    console.print(f"  Files processed: {payload.get('processed', 0)}")
    console.print(f"  Success: {summary.get('success', 0)}")
    console.print(f"  Failed: {summary.get('failed', 0)}")
    console.print(f"  Skipped: {summary.get('skipped', 0)}")

    failures = [
        r for r in (payload.get("results") or []) if r.get("status") == "failed"
    ]
    if failures:
        console.print("\n[bold]Failed files:[/bold]")
        for r in failures:
            console.print(
                f"  • {r.get('file', 'unknown')}: {r.get('error', 'unknown error')}"
            )
    console.print("=" * 80)
