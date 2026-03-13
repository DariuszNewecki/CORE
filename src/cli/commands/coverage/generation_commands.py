# src/cli/commands/coverage/generation_commands.py
"""Test generation commands - Pure V2 Adaptive Architecture."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()


# ID: b27c8ef7-9e92-4995-ae21-3a2f7d42b73d
def register_generation_commands(app: typer.Typer) -> None:
    """
    Register V2 test generation commands.

    LEGACY ELIMINATION: Removed 'accumulate' and 'remediate' commands
    per Roadmap Phase 2.
    """
    app.command("generate-adaptive")(generate_adaptive_command)
    app.command("generate-adaptive-batch")(generate_adaptive_batch_command)


@core_command(dangerous=True, confirmation=True)
# ID: 35d81f3f-de8f-4984-b9ab-0b311669268d
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
    from will.test_generation.adaptive_test_generator import (
        AdaptiveTestGenerator,
        TestGenerationResult,
    )

    core_context: CoreContext = ctx.obj
    logger.info("[bold cyan]🧪 Adaptive Test Generation (V2)[/bold cyan]\n")
    try:
        generator = AdaptiveTestGenerator(context=core_context)
        result: TestGenerationResult = await generator.generate_tests_for_file(
            file_path=file_path, write=write, max_failures_per_pattern=max_failures
        )
        sandbox_passed = getattr(result, "sandbox_passed", None)
        logger.info("\n[bold]📊 Generation Results:[/bold]")
        logger.info("  File: %s", result.file_path)
        logger.info("  Total symbols: %s", result.total_symbols)
        logger.info("  Validated tests: %s", result.tests_generated)
        if sandbox_passed is not None:
            logger.info("  Sandbox passed: %s", sandbox_passed)
        logger.info("  Sandbox failed: %s", result.tests_failed)
        logger.info("  Skipped: %s", result.tests_skipped)
        rate_color = "green" if result.success_rate > 0.5 else "yellow"
        logger.info(
            "  Validation rate: [%s]%s[/%s]",
            rate_color,
            result.success_rate,
            rate_color,
        )
        if result.strategy_switches > 0:
            logger.info(
                "  Strategy switches: [cyan]%s[/cyan]", result.strategy_switches
            )
        if result.patterns_learned:
            logger.info("\n[bold]🧠 Patterns Learned:[/bold]")
            for pattern, count in sorted(
                result.patterns_learned.items(), key=lambda x: x[1], reverse=True
            ):
                logger.info("  • %s: %sx", pattern, count)
        logger.info("\n⏱️  Duration: %ss", result.total_duration)
        if write:
            logger.info("\n[dim]Write mode:[/dim]")
            logger.info("  • Passing tests -> tests/... (mirrored)")
            logger.info("  • Failing tests  -> var/artifacts/test_gen/failures/...")
        if result.tests_generated > 0:
            logger.info("\n[bold green]✅ Completed generation cycle.[/bold green]")
        else:
            logger.info(
                "\n[bold yellow]⚠️  No tests validated successfully.[/bold yellow]"
            )
    except Exception as e:
        logger.error("Adaptive test generation failed: %s", e, exc_info=True)
        logger.info("[red]❌ Generation failed: %s[/red]", e)
        raise typer.Exit(code=1)


@core_command(dangerous=True, confirmation=True)
# ID: 4158a9ca-f87e-4311-8a02-ea8d5e696f40
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
    from body.quality.coverage_analyzer import CoverageAnalyzer
    from will.test_generation.adaptive_test_generator import AdaptiveTestGenerator

    core_context: CoreContext = ctx.obj
    repo_root = core_context.git_service.repo_path
    logger.info(
        "[bold cyan]🧪 Adaptive Test Generation - Batch Mode (V2)[/bold cyan]\n"
    )
    analyzer = CoverageAnalyzer(repo_path=repo_root)
    coverage_map = analyzer.get_module_coverage()
    all_files = list(repo_root.glob(pattern))

    # ID: a74712c6-0de0-4537-b3f9-e45810ef6281
    def get_coverage_score(file_path: Path) -> float:
        try:
            rel = str(file_path.relative_to(repo_root)).replace("\\", "/")
            return float(coverage_map.get(rel, 0.0))
        except (ValueError, KeyError):
            return 0.0

    eligible_files = [f for f in all_files if get_coverage_score(f) <= min_coverage]
    prioritized_files = sorted(eligible_files, key=get_coverage_score)[:limit]
    if not prioritized_files:
        logger.info(
            "[yellow]No files found matching: %s with coverage <= %s%[/yellow]",
            pattern,
            min_coverage,
        )
        return
    logger.info(
        "[cyan]Processing %s files (Lowest Coverage First)...[/cyan]",
        len(prioritized_files),
    )
    logger.info("[dim]Min coverage threshold: %s%[/dim]\n", min_coverage)
    total_symbols = 0
    total_validated = 0
    total_sandbox_passed = 0
    total_tests_saved = 0
    total_failed_files = 0
    start_time = time.time()
    generator = AdaptiveTestGenerator(context=core_context)
    for idx, file_path in enumerate(prioritized_files, 1):
        rel_path = file_path.relative_to(repo_root)
        current_coverage = get_coverage_score(file_path)
        logger.info(
            "\n[bold cyan][%s/%s][/bold cyan] %s (coverage: %s%)",
            idx,
            len(prioritized_files),
            rel_path,
            current_coverage,
        )
        try:
            result = await generator.generate_tests_for_file(
                file_path=str(rel_path), write=write, max_failures_per_pattern=3
            )
            total_symbols += result.total_symbols
            total_validated += result.tests_generated
            total_sandbox_passed += getattr(result, "sandbox_passed", 0)
            for test_result in result.generated_tests:
                if test_result.get("persisted") and test_result.get("persist_path"):
                    if "failures" not in test_result.get("persist_path", ""):
                        total_tests_saved += 1
            if result.tests_generated > 0:
                logger.info(
                    "  ✅ Validated: %s, Sandbox passed: %s",
                    result.tests_generated,
                    getattr(result, "sandbox_passed", 0),
                )
            else:
                logger.info("  ⚠️  No tests generated")
                total_failed_files += 1
        except Exception as e:
            logger.info("  ❌ Error: %s", e)
            total_failed_files += 1
            continue
    total_duration = time.time() - start_time
    logger.info("\n" + "=" * 80)
    logger.info("[bold]📊 Batch Generation Summary[/bold]\n")
    logger.info("  Files processed: %s", len(prioritized_files))
    logger.info("  Files failed: %s", total_failed_files)
    logger.info("  Total symbols: %s", total_symbols)
    logger.info("  Tests validated: %s", total_validated)
    logger.info("  Tests sandbox-passed: %s", total_sandbox_passed)
    if write:
        logger.info(
            "  [bold green]Tests saved to suite: %s[/bold green]", total_tests_saved
        )
    else:
        logger.info("  [dim]Tests saved: 0 (dry-run mode, use --write to save)[/dim]")
    logger.info("\n  Duration: %ss", total_duration)
    logger.info("  Avg per file: %ss", total_duration / len(prioritized_files))
    if total_tests_saved > 0:
        logger.info(
            "\n[bold green]✅ Successfully saved %s tests to your test suite![/bold green]",
            total_tests_saved,
        )
    elif write:
        logger.info(
            "\n[yellow]⚠️  No tests were saved (all failed validation or sandbox)[/yellow]"
        )
    logger.info("=" * 80)
