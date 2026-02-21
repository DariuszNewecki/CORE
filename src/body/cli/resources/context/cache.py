# src/body/cli/resources/context/cache.py
"""
Context cache command - Manage context cache.

Usage:
    core-admin context cache list
    core-admin context cache clear
    core-admin context cache stats
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

# Relative to repo root (cwd when running core-admin)
_CACHE_DIR = "work/context_cache"


# ID: 57a38e68-f500-4219-8a53-d1cd0d8f7c28
def cache(
    action: str = typer.Argument(
        ...,
        help="Action: list, clear, stats",
    ),
) -> None:
    """
    Manage context cache.

    Actions:
        list   - Show cached context queries
        clear  - Clear all cached contexts
        stats  - Show cache statistics (size, hit rate, etc.)

    Examples:
        core-admin context cache list
        core-admin context cache clear
        core-admin context cache stats

    The context cache stores built context packages to speed up
    repeated queries. Caching is automatically disabled when
    working with Shadow Truth (LimbWorkspace).
    """
    try:
        if action == "list":
            _list_cache()
        elif action == "clear":
            _clear_cache()
        elif action == "stats":
            _show_stats()
        else:
            console.print(f"[red]❌ Unknown action: {action}[/red]")
            console.print("[dim]Valid actions: list, clear, stats[/dim]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        logger.exception("Cache operation failed")
        raise typer.Exit(code=1)


def _get_cache_dir() -> Path:
    """Resolve the cache directory relative to cwd (repo root)."""
    return Path(_CACHE_DIR)


def _list_cache() -> None:
    """List all cached context queries."""
    cache_dir = _get_cache_dir()

    if not cache_dir.exists():
        console.print("[dim]Cache directory does not exist. No entries.[/dim]")
        return

    files = sorted(
        cache_dir.glob("*.yaml"), key=lambda f: f.stat().st_mtime, reverse=True
    )

    if not files:
        console.print("[dim]Cache is empty.[/dim]")
        return

    table = Table(
        title=f"Context Cache ({len(files)} entries)", header_style="bold cyan"
    )
    table.add_column("Key (short)", style="cyan", no_wrap=True)
    table.add_column("Modified", style="green")
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Age (h)", style="magenta", justify="right")

    now = datetime.now(UTC)
    for f in files:
        stat = f.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        age_h = (now - mtime).total_seconds() / 3600
        size_kb = stat.st_size / 1024
        table.add_row(
            f.stem[:16],
            mtime.strftime("%Y-%m-%d %H:%M"),
            f"{size_kb:.1f} KB",
            f"{age_h:.1f}",
        )

    console.print(table)


def _clear_cache() -> None:
    """Clear all cached contexts."""
    cache_dir = _get_cache_dir()

    if not cache_dir.exists() or not list(cache_dir.glob("*.yaml")):
        console.print("[dim]Cache is already empty.[/dim]")
        return

    count = len(list(cache_dir.glob("*.yaml")))
    console.print(
        f"[yellow]⚠️  This will delete {count} cached context package(s).[/yellow]"
    )

    if not typer.confirm("Continue?"):
        console.print("[dim]Aborted.[/dim]")
        return

    from shared.infrastructure.context.cache import ContextCache

    removed = ContextCache(str(cache_dir)).clear_all()
    console.print(f"[green]✅ Cleared {removed} cache entries.[/green]")


def _show_stats() -> None:
    """Show cache statistics."""
    cache_dir = _get_cache_dir()

    if not cache_dir.exists():
        console.print("[dim]Cache directory does not exist.[/dim]")
        return

    files = list(cache_dir.glob("*.yaml"))
    ttl_hours = 24

    now = datetime.now(UTC)
    total_size = 0
    expired = 0
    oldest_dt = None

    for f in files:
        stat = f.stat()
        total_size += stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        age_h = (now - mtime).total_seconds() / 3600
        if age_h > ttl_hours:
            expired += 1
        if oldest_dt is None or mtime < oldest_dt:
            oldest_dt = mtime

    table = Table(title="Context Cache Statistics", header_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total entries", str(len(files)))
    table.add_row("Total size", f"{total_size / 1024:.1f} KB")
    table.add_row("Expired entries", f"{expired} (TTL={ttl_hours}h)")
    table.add_row("Active entries", str(len(files) - expired))
    table.add_row(
        "Oldest entry",
        oldest_dt.strftime("%Y-%m-%d %H:%M") if oldest_dt else "—",
    )
    table.add_row("Cache dir", str(cache_dir))

    console.print(table)
