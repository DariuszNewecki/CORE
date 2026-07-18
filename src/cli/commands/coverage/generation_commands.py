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
            "Required — symbol-granular test generation has no dry-run mode "
            "and writes test files unconditionally. Must be passed "
            "explicitly; omitting it exits without calling the API (#809, #814)."
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
            "[red]This generation command writes test files "
            "unconditionally — there is no dry-run mode. Re-run with "
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

    # remediate_file_by_symbol()'s real shape (#814 — replaces the retired
    # EnhancedSingleFileRemediationService): {"status": "completed",
    # "source_file", "test_file", "summary": {"gaps","succeeded","failed",
    # "skipped"}, "results": [...per-symbol...], "files_produced": [...]}.
    # No final_coverage — the new pipeline generates per-symbol against
    # TestGapEvaluator's gap list rather than measuring whole-file coverage
    # after the fact; per-symbol pass/fail in "summary" is the replacement
    # signal.
    payload = final.get("result") or {}
    summary = payload.get("summary") or {}
    console.print("\n[bold]📊 Generation Results:[/bold]")
    console.print(f"  File: {payload.get('source_file', file_path)}")
    console.print(f"  Test file: {payload.get('test_file', 'unknown')}")
    console.print(
        f"  Symbols: {summary.get('succeeded', 0)}/{summary.get('gaps', 0)} generated"
        + (f", {summary.get('failed', 0)} failed" if summary.get("failed") else "")
    )
    for symbol_result in payload.get("results") or []:
        if not symbol_result.get("ok"):
            console.print(
                f"    [red]✗ {symbol_result.get('symbol_name', 'unknown')}[/red]: "
                f"{symbol_result.get('error', 'unknown error')}"
            )

    # final["status"] == "completed" (checked above) is the orchestration
    # lifecycle status — coverage_runs reached a controlled terminal state,
    # NOT that every symbol succeeded. That's a separate signal, in
    # summary.failed/summary.gaps, and must be checked independently:
    # a run with 0/7 generated is a "completed" run but not a successful one.
    gap_count = summary.get("gaps", 0)
    failed_count = summary.get("failed", 0)
    if gap_count == 0:
        console.print(
            "\n[bold green]✅ No untested public symbols — nothing to generate.[/bold green]"
        )
    elif failed_count == 0:
        console.print("\n[bold green]✅ Completed generation cycle.[/bold green]")
    else:
        console.print(
            f"\n[bold red]❌ {failed_count}/{gap_count} symbol(s) failed to generate "
            "— see failures above.[/bold red]"
        )
        raise typer.Exit(code=1)


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
            "Required — symbol-granular test generation has no dry-run mode "
            "and writes test files unconditionally. Must be passed "
            "explicitly; omitting it exits without calling the API (#809, #814)."
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
            "[red]This generation command writes test files "
            "unconditionally — there is no dry-run mode. Re-run with "
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

    # remediate_batch_by_symbol()'s real shape (#814 — replaces the retired
    # BatchRemediationService): {"status", "processed", "results": [...],
    # "summary": {"success","failed","skipped"}} — the top-level shape is
    # unchanged from the pre-#814 batch service, but each entry in "results"
    # now carries its own nested "summary" (a file with status="completed"
    # can still have partial per-symbol failures) rather than a flat
    # "success"/"failed"/"skipped" status string.
    payload = final.get("result") or {}
    summary = payload.get("summary") or {}
    console.print("\n" + "=" * 80)
    console.print("[bold]📊 Batch Generation Summary[/bold]\n")
    console.print(f"  Files processed: {payload.get('processed', 0)}")
    console.print(f"  Success: {summary.get('success', 0)}")
    console.print(f"  Failed: {summary.get('failed', 0)}")
    console.print(f"  Skipped: {summary.get('skipped', 0)}")

    failures = [
        r
        for r in (payload.get("results") or [])
        if r.get("status") != "completed" or (r.get("summary") or {}).get("failed")
    ]
    if failures:
        console.print("\n[bold]Failed files:[/bold]")
        for r in failures:
            error = r.get("error") or (
                f"{(r.get('summary') or {}).get('failed', 0)} symbol(s) failed"
            )
            console.print(f"  • {r.get('file', 'unknown')}: {error}")
    console.print("=" * 80)

    # Top-level "completed" (checked above) is orchestration lifecycle, not
    # per-file success — a batch with every file failing is still a
    # "completed" run. summary.failed is the actual success signal.
    if summary.get("failed", 0) > 0:
        raise typer.Exit(code=1)
