# src/cli/resources/runtime/health.py
"""
Runtime health command.

Provides a single-shot dashboard of the live CORE runtime:
  - Worker heartbeats + status
  - Observer health snapshot (findings, stale, silent, orphaned)
  - Blackboard pulse (status summary + recent entries)
  - Recent crawl stats
  - Blast radius top symbols
"""

from __future__ import annotations

from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import text

from shared.cli_utils import async_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

runtime_app = typer.Typer(
    help="Runtime state and health of the running CORE system.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _age(ts: datetime | None) -> str:
    """Human-readable age from a UTC-aware timestamp."""
    if ts is None:
        return "never"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    s = int((datetime.now(UTC) - ts).total_seconds())
    if s < 60:
        return f"{s}s ago"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


def _worker_colour(status: str, last_heartbeat: datetime | None) -> str:
    if status != "active":
        return "red"
    if last_heartbeat is None:
        return "yellow"
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=UTC)
    age_s = (datetime.now(UTC) - last_heartbeat).total_seconds()
    if age_s < 600:  # < 10 min — healthy
        return "green"
    if age_s < 3600:  # < 1 h — stale
        return "yellow"
    return "red"  # silent


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@runtime_app.command("health")
@async_command
# ID: 7f8a9b0c-1d2e-3f4a-5b6c-7d8e9f0a1b2c
async def health_cmd(
    plain: bool = typer.Option(
        False, "--plain", help="Plain text output (log/pipe friendly)."
    ),
) -> None:
    """
    Live health dashboard for the CORE runtime.

    Shows workers, observer snapshot, blackboard pulse,
    recent crawl stats, and blast radius top symbols.
    """
    async with get_session() as session:
        workers = (
            await session.execute(
                text(
                    """
            SELECT worker_name, worker_class, phase, status, last_heartbeat
            FROM core.worker_registry
            ORDER BY last_heartbeat DESC NULLS LAST
            """
                )
            )
        ).fetchall()

        bb_summary = (
            await session.execute(
                text(
                    """
            SELECT status, COUNT(*) AS cnt
            FROM core.blackboard_entries
            GROUP BY status
            ORDER BY cnt DESC
            """
                )
            )
        ).fetchall()

        bb_recent = (
            await session.execute(
                text(
                    """
            SELECT entry_type, subject, status, created_at
            FROM core.blackboard_entries
            ORDER BY created_at DESC
            LIMIT 8
            """
                )
            )
        ).fetchall()

        health = (
            await session.execute(
                text(
                    """
            SELECT observed_at, open_findings, stale_entries,
                   silent_workers, orphaned_symbols
            FROM core.system_health_log
            ORDER BY observed_at DESC
            LIMIT 1
            """
                )
            )
        ).fetchone()

        crawl = (
            await session.execute(
                text(
                    """
            SELECT started_at, status, files_scanned, files_changed, edges_created
            FROM core.crawl_runs
            ORDER BY started_at DESC
            LIMIT 3
            """
                )
            )
        ).fetchall()

        blast = (
            await session.execute(
                text(
                    """
            SELECT symbol_path, affected_symbol_count, direct_caller_count
            FROM core.v_symbol_blast_radius
            ORDER BY affected_symbol_count DESC
            LIMIT 10
            """
                )
            )
        ).fetchall()

    if plain:
        _render_plain(workers, bb_summary, bb_recent, health, crawl, blast)
    else:
        _render_rich(workers, bb_summary, bb_recent, health, crawl, blast)


# ---------------------------------------------------------------------------
# Rich renderer
# ---------------------------------------------------------------------------


def _render_rich(workers, bb_summary, bb_recent, health, crawl, blast) -> None:
    console.rule("[bold cyan]CORE Runtime Health[/bold cyan]")

    # Workers
    console.print("\n[bold]Workers[/bold]")
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Name")
    t.add_column("Class")
    t.add_column("Phase")
    t.add_column("Status")
    t.add_column("Last Heartbeat")
    for w in workers:
        c = _worker_colour(w.status, w.last_heartbeat)
        t.add_row(
            w.worker_name,
            w.worker_class,
            w.phase,
            f"[{c}]{w.status}[/{c}]",
            _age(w.last_heartbeat),
        )
    console.print(t)

    # Observer snapshot
    if health:
        console.print("\n[bold]Observer — Latest Snapshot[/bold]")
        t2 = Table(show_header=True, header_style="bold magenta")
        t2.add_column("Observed")
        t2.add_column("Open Findings")
        t2.add_column("Stale Entries")
        t2.add_column("Silent Workers")
        t2.add_column("Orphaned Symbols")
        t2.add_row(
            _age(health.observed_at),
            str(health.open_findings),
            str(health.stale_entries),
            str(health.silent_workers),
            str(health.orphaned_symbols),
        )
        console.print(t2)

    # Blackboard summary
    console.print("\n[bold]Blackboard[/bold]")
    t3 = Table(show_header=True, header_style="bold magenta")
    t3.add_column("Status")
    t3.add_column("Count")
    for row in bb_summary:
        t3.add_row(row.status, str(row.cnt))
    console.print(t3)

    # Blackboard recent
    console.print("\n[bold]Blackboard — Recent Entries[/bold]")
    t4 = Table(show_header=True, header_style="bold magenta")
    t4.add_column("Type")
    t4.add_column("Subject")
    t4.add_column("Status")
    t4.add_column("Age")
    for e in bb_recent:
        t4.add_row(e.entry_type, e.subject, e.status, _age(e.created_at))
    console.print(t4)

    # Crawl stats
    console.print("\n[bold]Recent Crawls[/bold]")
    t5 = Table(show_header=True, header_style="bold magenta")
    t5.add_column("Started")
    t5.add_column("Status")
    t5.add_column("Files Scanned")
    t5.add_column("Files Changed")
    t5.add_column("Edges Created")
    for c in crawl:
        t5.add_row(
            _age(c.started_at),
            c.status,
            str(c.files_scanned),
            str(c.files_changed),
            str(c.edges_created),
        )
    console.print(t5)

    # Blast radius
    console.print("\n[bold]Blast Radius — Top Symbols[/bold]")
    t6 = Table(show_header=True, header_style="bold magenta")
    t6.add_column("Symbol Path")
    t6.add_column("Affected", justify="right")
    t6.add_column("Direct Callers", justify="right")
    for b in blast:
        t6.add_row(
            b.symbol_path,
            str(b.affected_symbol_count),
            str(b.direct_caller_count),
        )
    console.print(t6)

    console.rule()


# ---------------------------------------------------------------------------
# Plain renderer
# ---------------------------------------------------------------------------


def _render_plain(workers, bb_summary, bb_recent, health, crawl, blast) -> None:
    print("=== CORE Runtime Health ===\n")

    print("-- Workers --")
    for w in workers:
        print(f"  {w.worker_name:<30} {w.status:<10} {_age(w.last_heartbeat)}")

    if health:
        print("\n-- Observer (latest) --")
        print(f"  observed:         {_age(health.observed_at)}")
        print(f"  open_findings:    {health.open_findings}")
        print(f"  stale_entries:    {health.stale_entries}")
        print(f"  silent_workers:   {health.silent_workers}")
        print(f"  orphaned_symbols: {health.orphaned_symbols}")

    print("\n-- Blackboard --")
    for row in bb_summary:
        print(f"  {row.status:<12} {row.cnt}")

    print("\n-- Recent Blackboard Entries --")
    for e in bb_recent:
        print(
            f"  {e.entry_type:<12} {e.subject:<40} {e.status:<10} {_age(e.created_at)}"
        )

    print("\n-- Recent Crawls --")
    for c in crawl:
        print(
            f"  {_age(c.started_at):<12} {c.status:<12} "
            f"scanned={c.files_scanned} changed={c.files_changed} edges={c.edges_created}"
        )

    print("\n-- Blast Radius Top Symbols --")
    for b in blast:
        print(
            f"  affected={b.affected_symbol_count:<5} "
            f"callers={b.direct_caller_count:<5} {b.symbol_path}"
        )
