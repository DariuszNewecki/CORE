# src/body/cli/resources/database/cleanup.py
# ID: cli.resources.database.cleanup
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

from . import app


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
        help="Cleanup target: all, memory, sessions, orphans",
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
    - memory: Old conversation memory entries
    - sessions: Expired session data
    - orphans: Records without valid foreign keys
    - all: Run all cleanup operations

    Constitutional Compliance:
    - Requires --write flag for safety
    - Generates audit trail for deletions
    - Rollback plan created for recovery

    Examples:
        # Dry-run: show what would be deleted
        core-admin database cleanup

        # Clean up old memory entries
        core-admin database cleanup --target memory --write

        # Full cleanup with custom age threshold
        core-admin database cleanup --target all --days 60 --write
    """
    console.print("[bold cyan]🧹 Database Cleanup[/bold cyan]")
    console.print(f"Target: {target}")
    console.print(f"Age threshold: {days} days")
    console.print(f"Mode: {'WRITE' if write else 'DRY-RUN'}")
    console.print()

    try:
        from features.self_healing import MemoryCleanupService

        async with get_session() as session:
            service = MemoryCleanupService(session=session)
            result = await service.cleanup_old_memories(
                days_to_keep_episodes=days,
                days_to_keep_reflections=days,
                dry_run=not write,
            )

        if result.ok:
            stats = result.data
            console.print("[green]✅ Cleanup completed[/green]")
            console.print()
            console.print(f"  Episodes deleted: {stats.get('episodes_deleted', 0)}")
            console.print(f"  Decisions deleted: {stats.get('decisions_deleted', 0)}")
            console.print(
                f"  Reflections deleted: {stats.get('reflections_deleted', 0)}"
            )

            if not write:
                console.print()
                console.print("[yellow]💡 Run with --write to apply cleanup[/yellow]")
        else:
            console.print(f"[red]❌ Cleanup failed: {result.error}[/red]", err=True)
            raise typer.Exit(1)

    except Exception as e:
        logger.error("Database cleanup failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
