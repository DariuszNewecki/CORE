# src/cli/resources/database/cleanup.py
"""
Database cleanup command.

Removes orphaned records, expired sessions, and stale data.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("cleanup")
@core_command(dangerous=True, requires_context=False)
# ID: 4f8a2d7e-9c3b-4a1e-8d5f-7b2e9d6c3a4f
async def cleanup_database(
    ctx: typer.Context,
    write: bool = typer.Option(
        False,
        "--write",
        help="Apply cleanup (default: dry-run)",
    ),
    target: str = typer.Option(
        "all",
        "--target",
        "-t",
        help="Cleanup target: all, memory, action_results",
    ),
    days: int = typer.Option(
        30,
        "--days",
        "-d",
        help="Age threshold in days for stale data removal",
    ),
) -> None:
    """
    Remove orphaned and stale database records.

    Cleanup targets:
    - memory: Old agent episode and reflection entries
    - action_results: Old records from core.action_results ledger
    - all: Run all cleanup operations

    Constitutional Compliance:
    - Requires --write flag for safety
    - Generates audit trail for deletions

    Examples:
        # Dry-run: show what would be deleted
        core-admin database cleanup

        # Clean up old memory entries
        core-admin database cleanup --target memory --write

        # Full cleanup with custom age threshold
        core-admin database cleanup --target all --days 60 --write
    """
    from body.maintenance.memory_cleanup_service import MemoryCleanupService

    console.print("[bold cyan]🧹 Database Cleanup[/bold cyan]")
    console.print(f"Target: {target}")
    console.print(f"Age threshold: {days} days")
    console.print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    console.print()

    try:
        async with get_session() as session:
            service = MemoryCleanupService(session=session)

            if target in ("all", "memory"):
                result = await service.cleanup_old_memories(
                    days_to_keep_episodes=days,
                    days_to_keep_reflections=days * 3,
                    dry_run=not write,
                )
                if result.ok:
                    stats = result.data
                    console.print("[green]✅ Memory cleanup completed[/green]")
                    console.print(f"  Episodes: {stats.get('episodes_deleted', 0)}")
                    console.print(
                        f"  Reflections: {stats.get('reflections_deleted', 0)}"
                    )
                else:
                    console.print(
                        f"[red]❌ Memory cleanup failed: {result.data.get('error')}[/red]",
                        err=True,
                    )

            if target in ("all", "action_results"):
                result = await service.cleanup_action_results(
                    days_to_keep=days,
                    dry_run=not write,
                )
                if result.ok:
                    stats = result.data
                    console.print("[green]✅ Action results cleanup completed[/green]")
                    console.print(f"  Records: {stats.get('records_processed', 0)}")
                else:
                    console.print(
                        f"[red]❌ Action results cleanup failed: {result.data.get('error')}[/red]",
                        err=True,
                    )

        if not write:
            console.print()
            console.print("[yellow]💡 Run with --write to apply cleanup[/yellow]")

    except Exception as e:
        logger.error("Database cleanup failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
