# src/body/cli/commands/dev_sync.py
"""
Dev sync workflow orchestrator.

Replaces the Makefile's dev-sync target with a governed Python workflow.
Commands with CommandResult (fix ids, fix headers) use internal functions.
Other commands call CLI for now - will migrate incrementally.
"""

from __future__ import annotations

import subprocess
import time

import typer
from rich.console import Console
from shared.activity_logging import activity_run
from shared.cli_types import CommandResult
from shared.cli_utils import async_command
from shared.config import settings

from body.cli.commands.fix.code_style import fix_headers_internal

# Import the internal functions that have been migrated
from body.cli.commands.fix.metadata import fix_ids_internal
from body.cli.workflows.dev_sync_reporter import DevSyncReporter

console = Console()

dev_sync_app = typer.Typer(
    help="Development synchronization workflows",
    no_args_is_help=True,
)


# ID: 9648c1b8-d1e4-442e-aac5-9202ba527d6b
def run_cli_command(command: str, name: str) -> CommandResult:
    """
    Wrapper to run existing CLI commands that haven't been migrated yet.

    Returns a CommandResult for consistency with the reporter.
    Once commands are migrated to CommandResult, replace these calls.
    """
    start_time = time.time()

    try:
        result = subprocess.run(
            f"poetry run core-admin {command}",
            shell=True,
            capture_output=True,
            text=True,
            check=True,
        )

        return CommandResult(
            name=name,
            ok=True,
            data={
                "command": command,
                "output": result.stdout.strip()[:100] if result.stdout else "",
            },
            duration_sec=time.time() - start_time,
        )

    except subprocess.CalledProcessError as e:
        return CommandResult(
            name=name,
            ok=False,
            data={
                "command": command,
                "error": e.stderr.strip()[:100] if e.stderr else str(e),
                "exit_code": e.returncode,
            },
            duration_sec=time.time() - start_time,
        )


@dev_sync_app.command("sync")
@async_command
# ID: dev_sync_command_v1
# ID: a45c297a-6e3d-42a1-aa1f-53d7039933f1
async def dev_sync_command(
    write: bool = typer.Option(
        True,
        "--write/--dry-run",
        help="Apply changes (default) or dry-run only",
    ),
) -> None:
    """
    Run the comprehensive dev-sync workflow.

    This orchestrates all dev-sync steps in a governed manner,
    with proper phase reporting and activity logging.

    Phases:
    1. Code Fixers - IDs, headers, docstrings, formatting
    2. Quality Checks - Linting
    3. Database Sync - Vectors and knowledge
    4. Vectorization - Build embeddings
    5. Analysis - Find duplicates
    """

    write_flag = "--write" if write else "--dry-run"

    with activity_run("dev.sync") as run:
        reporter = DevSyncReporter(run, repo_path=str(settings.REPO_PATH))
        reporter.print_header()

        # =================================================================
        # PHASE 1: CODE FIXERS
        # =================================================================
        phase = reporter.start_phase("Code Fixers")

        # Step 1: Assign missing IDs (migrated ✅)
        result = await fix_ids_internal(write=write)
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # Step 2: Fix headers (migrated ✅)
        result = await fix_headers_internal(write=write)
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # Step 3: Fix docstrings (TODO: migrate to CommandResult)
        with console.status("[cyan]Fixing docstrings...[/cyan]"):
            result = run_cli_command(f"fix docstrings {write_flag}", "fix.docstrings")
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # Step 4: Format code style (TODO: migrate to CommandResult)
        with console.status("[cyan]Formatting code...[/cyan]"):
            result = run_cli_command("fix code-style", "fix.code-style")
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # =================================================================
        # PHASE 2: QUALITY CHECKS
        # =================================================================
        phase = reporter.start_phase("Quality Checks")

        # Step 5: Run linter (TODO: migrate to CommandResult)
        with console.status("[cyan]Running linter...[/cyan]"):
            result = run_cli_command("check lint", "check.lint")
        reporter.record_result(result, phase)
        if not result.ok:
            console.print("[yellow]⚠ Lint failures detected, continuing...[/yellow]")
            # Note: We continue even if lint fails (non-blocking)

        # =================================================================
        # PHASE 3: DATABASE SYNC
        # =================================================================
        phase = reporter.start_phase("Database Sync")

        # Step 6: Sync vectors (TODO: migrate to CommandResult)
        with console.status("[cyan]Synchronizing vectors...[/cyan]"):
            result = run_cli_command(f"fix vector-sync {write_flag}", "fix.vector-sync")
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # Step 7: Sync knowledge (TODO: migrate to CommandResult)
        with console.status("[cyan]Syncing knowledge to database...[/cyan]"):
            result = run_cli_command(
                f"manage database sync-knowledge {write_flag}", "manage.sync-knowledge"
            )
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # Step 8: Define symbols (TODO: migrate to CommandResult)
        with console.status("[cyan]Defining capabilities...[/cyan]"):
            result = run_cli_command("manage define-symbols", "manage.define-symbols")
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(
                "[yellow]⚠ Symbol definition had issues, continuing...[/yellow]"
            )
            # Note: Non-blocking

        # =================================================================
        # PHASE 4: VECTORIZATION
        # =================================================================
        phase = reporter.start_phase("Vectorization")

        # Step 9: Vectorize knowledge graph (TODO: migrate to CommandResult)
        with console.status("[cyan]Vectorizing knowledge graph...[/cyan]"):
            result = run_cli_command(f"run vectorize {write_flag}", "run.vectorize")
        reporter.record_result(result, phase)
        if not result.ok:
            console.print(f"[red]✗ {result.name} failed, aborting workflow[/red]")
            reporter.print_phases()
            reporter.print_summary()
            raise typer.Exit(1)

        # =================================================================
        # PHASE 5: ANALYSIS
        # =================================================================
        phase = reporter.start_phase("Code Analysis")

        # Step 10: Find duplicates (TODO: migrate to CommandResult)
        with console.status("[cyan]Detecting duplicate code...[/cyan]"):
            result = run_cli_command(
                "inspect duplicates --threshold 0.96", "inspect.duplicates"
            )
        reporter.record_result(result, phase)
        # Note: Duplicates check is informational, non-blocking

        # =================================================================
        # FINAL REPORT
        # =================================================================
        reporter.print_phases()
        reporter.print_summary()

        # Exit with appropriate code (only critical failures cause exit)
        critical_failures = [
            r
            for p in reporter.phases
            for r in p.results
            if not r.ok
            and r.name
            not in ["check.lint", "manage.define-symbols", "inspect.duplicates"]
        ]

        if critical_failures:
            raise typer.Exit(1)
