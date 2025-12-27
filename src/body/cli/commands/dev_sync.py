# src/body/cli/commands/dev_sync.py
# ID: cli.commands.dev_sync
"""
Dev sync workflow orchestrator.

Replaces the Makefile's dev-sync target with a governed Python workflow.
Refactored to use direct service calls (Internal Orchestration) instead of subprocesses.

CONSTITUTIONAL GUARDRail:
- BODY MUST treat `.intent/` as READ-ONLY.
- This workflow MUST NOT write to `.intent/` under any circumstances.
"""

from __future__ import annotations

import typer
from rich.console import Console

from body.cli.workflows.dev_sync_phases import DevSyncPhases
from body.cli.workflows.dev_sync_reporter import DevSyncReporter
from shared.activity_logging import activity_run
from shared.cli_utils import core_command
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session


console = Console()

dev_sync_app = typer.Typer(
    help="Development synchronization workflows",
    no_args_is_help=True,
)


@dev_sync_app.command("sync")
@core_command(dangerous=True, confirmation=True)
# ID: 5e95ba26-057d-4e7c-b84c-75f7cc5091e0
async def dev_sync_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write/--dry-run",
        help="Dry-run by default; use --write to apply changes",
    ),
) -> None:
    """
    Run the comprehensive dev-sync workflow.

    By default this runs in DRY-RUN mode (no writes).
    Pass --write to apply changes to the repository and related indices.

    GUARDRail:
    - `.intent/` is read-only for BODY. This workflow does not write to `.intent/`.
    """
    core_context: CoreContext = ctx.obj
    dry_run = not write

    with activity_run("dev.sync") as run:
        reporter = DevSyncReporter(run, repo_path=str(settings.REPO_PATH))
        reporter.print_header()

        # Initialize phase executor with dependencies
        phases = DevSyncPhases(
            core_context=core_context,
            reporter=reporter,
            console=console,
            write=write,
            dry_run=dry_run,
            session_factory=get_session,  # DI: pass session factory
        )

        # Execute all phases
        try:
            await phases.run_code_fixers()
            await phases.run_quality_checks()
            await phases.run_body_contracts()
            await phases.run_database_sync()
            await phases.run_vectorization()
            await phases.run_code_analysis()
        except typer.Exit:
            # Let typer.Exit propagate
            raise
        except Exception as e:
            console.print(f"[red]Fatal error in workflow: {e}[/red]")
            raise typer.Exit(1)

        # Print final report
        reporter.print_phases()
        reporter.print_summary()

        # Check for critical failures
        if phases.has_critical_failures():
            raise typer.Exit(1)


@dev_sync_app.command("fix-logging")
@core_command(dangerous=True, confirmation=True)
# ID: 0958b077-78bb-40ff-92bb-8a94f41a36db
async def fix_logging_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write/--dry-run", help="Apply fixes (default: dry-run)"
    ),
) -> None:
    """
    Fix logging standards violations (LOG-001, LOG-004).

    Converts console.print/status to logger calls in logic layers.
    """
    from body.cli.commands.fix_logging import LoggingFixer

    dry_run = not write
    fixer = LoggingFixer(settings.REPO_PATH, dry_run=dry_run)

    console.print("[bold cyan]Fixing Logging Violations[/bold cyan]")
    console.print(f"Mode: {'DRY RUN' if dry_run else 'WRITE'}")

    result = fixer.fix_all()

    console.print("\n[bold]Results:[/bold]")
    console.print(f"  Files modified: {result['files_modified']}")
    console.print(f"  Fixes applied: {result['fixes_applied']}")

    if dry_run:
        console.print(
            "\n[yellow]DRY RUN complete. Use --write to apply changes.[/yellow]"
        )
    else:
        console.print("\n[green]✓ Logging fixes applied successfully.[/green]")
