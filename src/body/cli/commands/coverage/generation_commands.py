# src/body/cli/commands/coverage/generation_commands.py
"""Test generation commands - Pure V2 Adaptive Architecture."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: 17b95400-ab72-4f44-8a79-64bf75d93a0f
def register_generation_commands(app: typer.Typer) -> None:
    """
    Register V2 test generation commands.

    LEGACY ELIMINATION: Removed 'accumulate' and 'remediate' commands
    per Roadmap Phase 2.
    """
    app.command("generate-adaptive")(generate_adaptive_command)
    app.command("generate-adaptive-batch")(generate_adaptive_batch_command)


@core_command(dangerous=True, confirmation=True)
# ID: a7d1c24e-3f5b-4b1a-9d2c-8e4f1a2b3c4d
async def generate_adaptive_command(
    ctx: typer.Context,
    file_path: str = typer.Argument(..., help="Source file to generate tests for"),
    write: bool = typer.Option(
        False,
        "--write",
        help="Promote sandbox-passing tests to /tests (mirror src/). Route failures to var/artifacts/.",
    ),
    max_failures: int = typer.Option(
        3, "--max-failures", help="Switch strategy after N failures with same pattern"
    ),
) -> None:
    """
    Generate tests using adaptive learning (V2 - Component Architecture).

    Delivery model (when --write is used):
    - Passing sandbox tests are promoted to mirrored paths under /tests (Verified Truth).
    - Failing sandbox tests are quarantined under var/artifacts/test_gen/failures/ (Morgue).
    """
    from features.test_generation_v2 import AdaptiveTestGenerator, TestGenerationResult

    core_context: CoreContext = ctx.obj

    console.print("[bold cyan]🧪 Adaptive Test Generation (V2)[/bold cyan]\n")

    try:
        generator = AdaptiveTestGenerator(context=core_context)

        result: TestGenerationResult = await generator.generate_tests_for_file(
            file_path=file_path,
            write=write,
            max_failures_per_pattern=max_failures,
        )

        sandbox_passed = getattr(result, "sandbox_passed", None)

        console.print("\n[bold]📊 Generation Results:[/bold]")
        console.print(f"  File: {result.file_path}")
        console.print(f"  Total symbols: {result.total_symbols}")

        # Interpret counts with Promotion/Morgue semantics
        console.print(f"  Validated tests: {result.tests_generated}")
        if sandbox_passed is not None:
            console.print(f"  Sandbox passed: {sandbox_passed}")
        console.print(f"  Sandbox failed: {result.tests_failed}")
        console.print(f"  Skipped: {result.tests_skipped}")

        rate_color = "green" if result.success_rate > 0.5 else "yellow"
        console.print(
            f"  Validation rate: [{rate_color}]{result.success_rate:.1%}[/{rate_color}]"
        )

        if result.strategy_switches > 0:
            console.print(
                f"  Strategy switches: [cyan]{result.strategy_switches}[/cyan]"
            )

        if result.patterns_learned:
            console.print("\n[bold]🧠 Patterns Learned:[/bold]")
            for pattern, count in sorted(
                result.patterns_learned.items(), key=lambda x: x[1], reverse=True
            ):
                console.print(f"  • {pattern}: {count}x")

        console.print(f"\n⏱️  Duration: {result.total_duration:.2f}s")

        if write:
            console.print("\n[dim]Write mode:[/dim]")
            console.print("  • Passing tests -> tests/... (mirrored)")
            console.print("  • Failing tests  -> var/artifacts/test_gen/failures/...")

        if result.tests_generated > 0:
            console.print("\n[bold green]✅ Completed generation cycle.[/bold green]")
        else:
            console.print(
                "\n[bold yellow]⚠️  No tests validated successfully.[/bold yellow]"
            )

    except Exception as e:
        logger.error("Adaptive test generation failed: %s", e, exc_info=True)
        console.print(f"[red]❌ Generation failed: {e}[/red]")
        raise typer.Exit(code=1)


@core_command(dangerous=True, confirmation=True)
# ID: b8c9d0e1-f2a3-4b5c-6d7e-8f9a0b1c2d3e
async def generate_adaptive_batch_command(
    ctx: typer.Context,
    pattern: str = typer.Option("src/**/*.py", help="File pattern to match"),
    limit: int = typer.Option(10, help="Max files to process"),
    write: bool = typer.Option(False, "--write", help="Save passing tests"),
    min_coverage: float = typer.Option(
        0.0, help="Only process files below this coverage %"
    ),
) -> None:
    """
    Generate tests for multiple files using adaptive V2 system.

    Prioritizes files with lowest coverage first.
    """
    from features.self_healing.coverage_analyzer import CoverageAnalyzer
    from features.test_generation_v2 import AdaptiveTestGenerator

    core_context: CoreContext = ctx.obj

    console.print(
        "[bold cyan]🧪 Adaptive Test Generation - Batch Mode (V2)[/bold cyan]\n"
    )

    # Get coverage data
    analyzer = CoverageAnalyzer()
    coverage_map = analyzer.get_module_coverage()

    # Find matching files
    all_files = list(settings.REPO_PATH.glob(pattern))

    # Filter and sort by coverage
    # ID: fa722b9a-ede7-4419-9ba5-e5cdafdd8f3c
    def get_coverage_score(file_path: Path) -> float:
        try:
            rel = str(file_path.relative_to(settings.REPO_PATH)).replace("\\", "/")
            return float(coverage_map.get(rel, 0.0))
        except (ValueError, KeyError):
            return 0.0

    # Filter by min_coverage threshold
    eligible_files = [f for f in all_files if get_coverage_score(f) <= min_coverage]

    # Sort by coverage (lowest first) and limit
    prioritized_files = sorted(eligible_files, key=get_coverage_score)[:limit]

    if not prioritized_files:
        console.print(
            f"[yellow]No files found matching: {pattern} with coverage <= {min_coverage}%[/yellow]"
        )
        return

    console.print(
        f"[cyan]Processing {len(prioritized_files)} files (Lowest Coverage First)...[/cyan]"
    )
    console.print(f"[dim]Min coverage threshold: {min_coverage}%[/dim]\n")

    # Track totals
    total_symbols = 0
    total_validated = 0
    total_sandbox_passed = 0
    total_tests_saved = 0
    total_failed_files = 0
    start_time = time.time()

    generator = AdaptiveTestGenerator(context=core_context)

    for idx, file_path in enumerate(prioritized_files, 1):
        rel_path = file_path.relative_to(settings.REPO_PATH)
        current_coverage = get_coverage_score(file_path)

        console.print(
            f"\n[bold cyan][{idx}/{len(prioritized_files)}][/bold cyan] {rel_path} (coverage: {current_coverage:.1f}%)"
        )

        try:
            result = await generator.generate_tests_for_file(
                file_path=str(rel_path),
                write=write,
                max_failures_per_pattern=3,
            )

            # Accumulate stats
            total_symbols += result.total_symbols
            total_validated += result.tests_generated
            total_sandbox_passed += getattr(result, "sandbox_passed", 0)

            # Count tests actually saved (from persistence results)
            for test_result in result.generated_tests:
                if test_result.get("persisted") and test_result.get("persist_path"):
                    # Check if it's not in morgue
                    if "failures" not in test_result.get("persist_path", ""):
                        total_tests_saved += 1

            if result.tests_generated > 0:
                console.print(
                    f"  ✅ Validated: {result.tests_generated}, Sandbox passed: {getattr(result, 'sandbox_passed', 0)}"
                )
            else:
                console.print("  ⚠️  No tests generated")
                total_failed_files += 1

        except Exception as e:
            console.print(f"  ❌ Error: {e}")
            total_failed_files += 1
            continue

    # Final summary
    total_duration = time.time() - start_time

    console.print("\n" + "=" * 80)
    console.print("[bold]📊 Batch Generation Summary[/bold]\n")
    console.print(f"  Files processed: {len(prioritized_files)}")
    console.print(f"  Files failed: {total_failed_files}")
    console.print(f"  Total symbols: {total_symbols}")
    console.print(f"  Tests validated: {total_validated}")
    console.print(f"  Tests sandbox-passed: {total_sandbox_passed}")

    if write:
        console.print(
            f"  [bold green]Tests saved to suite: {total_tests_saved}[/bold green]"
        )
    else:
        console.print("  [dim]Tests saved: 0 (dry-run mode, use --write to save)[/dim]")

    console.print(f"\n  Duration: {total_duration:.1f}s")
    console.print(f"  Avg per file: {total_duration/len(prioritized_files):.1f}s")

    if total_tests_saved > 0:
        console.print(
            f"\n[bold green]✅ Successfully saved {total_tests_saved} tests to your test suite![/bold green]"
        )
    elif write:
        console.print(
            "\n[yellow]⚠️  No tests were saved (all failed validation or sandbox)[/yellow]"
        )

    console.print("=" * 80)
