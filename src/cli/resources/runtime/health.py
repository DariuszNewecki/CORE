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
    help="Runtime state and health of the running CORE system.", no_args_is_help=True
)


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
    if age_s < 600:
        return "green"
    if age_s < 3600:
        return "yellow"
    return "red"


@runtime_app.command("health")
@async_command
# ID: 38e31fa3-0c8c-4721-aeaa-57562292cf9f
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
                    "\n            SELECT worker_name, worker_class, phase, status, last_heartbeat\n            FROM core.worker_registry\n            ORDER BY last_heartbeat DESC NULLS LAST\n            "
                )
            )
        ).fetchall()
        bb_summary = (
            await session.execute(
                text(
                    "\n            SELECT status, COUNT(*) AS cnt\n            FROM core.blackboard_entries\n            GROUP BY status\n            ORDER BY cnt DESC\n            "
                )
            )
        ).fetchall()
        bb_recent = (
            await session.execute(
                text(
                    "\n            SELECT entry_type, subject, status, created_at\n            FROM core.blackboard_entries\n            ORDER BY created_at DESC\n            LIMIT 8\n            "
                )
            )
        ).fetchall()
        health = (
            await session.execute(
                text(
                    "\n            SELECT observed_at, open_findings, stale_entries,\n                   silent_workers, orphaned_symbols\n            FROM core.system_health_log\n            ORDER BY observed_at DESC\n            LIMIT 1\n            "
                )
            )
        ).fetchone()
        crawl = (
            await session.execute(
                text(
                    "\n            SELECT started_at, status, files_scanned, files_changed, edges_created\n            FROM core.crawl_runs\n            ORDER BY started_at DESC\n            LIMIT 3\n            "
                )
            )
        ).fetchall()
        blast = (
            await session.execute(
                text(
                    "\n            SELECT symbol_path, affected_symbol_count, direct_caller_count\n            FROM core.v_symbol_blast_radius\n            ORDER BY affected_symbol_count DESC\n            LIMIT 10\n            "
                )
            )
        ).fetchall()
    if plain:
        _render_plain(workers, bb_summary, bb_recent, health, crawl, blast)
    else:
        _render_rich(workers, bb_summary, bb_recent, health, crawl, blast)


def _render_rich(workers, bb_summary, bb_recent, health, crawl, blast) -> None:
    console.rule("[bold cyan]CORE Runtime Health[/bold cyan]")
    logger.info("\n[bold]Workers[/bold]")
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
    logger.info(t)
    if health:
        logger.info("\n[bold]Observer — Latest Snapshot[/bold]")
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
        logger.info(t2)
    logger.info("\n[bold]Blackboard[/bold]")
    t3 = Table(show_header=True, header_style="bold magenta")
    t3.add_column("Status")
    t3.add_column("Count")
    for row in bb_summary:
        t3.add_row(row.status, str(row.cnt))
    logger.info(t3)
    logger.info("\n[bold]Blackboard — Recent Entries[/bold]")
    t4 = Table(show_header=True, header_style="bold magenta")
    t4.add_column("Type")
    t4.add_column("Subject")
    t4.add_column("Status")
    t4.add_column("Age")
    for e in bb_recent:
        t4.add_row(e.entry_type, e.subject, e.status, _age(e.created_at))
    logger.info(t4)
    logger.info("\n[bold]Recent Crawls[/bold]")
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
    logger.info(t5)
    logger.info("\n[bold]Blast Radius — Top Symbols[/bold]")
    t6 = Table(show_header=True, header_style="bold magenta")
    t6.add_column("Symbol Path")
    t6.add_column("Affected", justify="right")
    t6.add_column("Direct Callers", justify="right")
    for b in blast:
        t6.add_row(
            b.symbol_path, str(b.affected_symbol_count), str(b.direct_caller_count)
        )
    logger.info(t6)
    console.rule()


def _render_plain(workers, bb_summary, bb_recent, health, crawl, blast) -> None:
    logger.info("=== CORE Runtime Health ===\n")
    logger.info("-- Workers --")
    for w in workers:
        logger.info(
            "  %s %s %s",
            w.worker_name.ljust(30),
            w.status.ljust(10),
            _age(w.last_heartbeat),
        )
    if health:
        logger.info("\n-- Observer (latest) --")
        logger.info("  observed:         %s", _age(health.observed_at))
        logger.info("  open_findings:    %s", health.open_findings)
        logger.info("  stale_entries:    %s", health.stale_entries)
        logger.info("  silent_workers:   %s", health.silent_workers)
        logger.info("  orphaned_symbols: %s", health.orphaned_symbols)
    logger.info("\n-- Blackboard --")
    for row in bb_summary:
        logger.info("  %s %s", row.status.ljust(12), row.cnt)
    logger.info("\n-- Recent Blackboard Entries --")
    for e in bb_recent:
        logger.info(
            "  %s %s %s %s",
            e.entry_type.ljust(12),
            e.subject.ljust(40),
            e.status.ljust(10),
            _age(e.created_at),
        )
    logger.info("\n-- Recent Crawls --")
    for c in crawl:
        logger.info(
            "  %s %s scanned=%s changed=%s edges=%s",
            _age(c.started_at).ljust(12),
            c.status.ljust(12),
            c.files_scanned,
            c.files_changed,
            c.edges_created,
        )
    logger.info("\n-- Blast Radius Top Symbols --")
    for b in blast:
        logger.info(
            "  affected=%-5s callers=%-5s %s",
            b.affected_symbol_count,
            b.direct_caller_count,
            b.symbol_path,
        )
