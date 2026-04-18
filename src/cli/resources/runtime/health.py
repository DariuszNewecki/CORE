# src/cli/resources/runtime/health.py
"""
Runtime health and dashboard commands.

Provides a single-shot dashboard of the live CORE runtime:
  - Worker heartbeats + status
  - Observer health snapshot (findings, stale, silent, orphaned)
  - Blackboard pulse (status summary + recent entries)
  - Recent crawl stats
  - Blast radius top symbols

Also provides a five-panel governor dashboard:
  - Convergence direction
  - Governor inbox
  - Loop running
  - Pipeline moving
  - Governance coverage
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

from cli.utils import async_command
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
    console.print("\n[bold]Blackboard[/bold]")
    t3 = Table(show_header=True, header_style="bold magenta")
    t3.add_column("Status")
    t3.add_column("Count")
    for row in bb_summary:
        t3.add_row(row.status, str(row.cnt))
    console.print(t3)
    console.print("\n[bold]Blackboard — Recent Entries[/bold]")
    t4 = Table(show_header=True, header_style="bold magenta")
    t4.add_column("Type")
    t4.add_column("Subject")
    t4.add_column("Status")
    t4.add_column("Age")
    for e in bb_recent:
        t4.add_row(e.entry_type, e.subject, e.status, _age(e.created_at))
    console.print(t4)
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
    console.print("\n[bold]Blast Radius — Top Symbols[/bold]")
    t6 = Table(show_header=True, header_style="bold magenta")
    t6.add_column("Symbol Path")
    t6.add_column("Affected", justify="right")
    t6.add_column("Direct Callers", justify="right")
    for b in blast:
        t6.add_row(
            b.symbol_path, str(b.affected_symbol_count), str(b.direct_caller_count)
        )
    console.print(t6)
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


# ---------------------------------------------------------------------------
# Governor Dashboard
# ---------------------------------------------------------------------------

_SIGNAL_STYLE = {
    "green": "bold green",
    "blue": "bold blue",
    "amber": "bold yellow",
    "red": "bold red",
    "grey": "dim",
}

_SIGNAL_EMOJI = {
    "green": "🟢",
    "blue": "🔵",
    "amber": "🟡",
    "red": "🔴",
    "grey": "⚪",
}


# ID: 25ad54a6-9889-4a66-91dc-05ba912c679f
def _make_panel(
    title: str,
    signal: str,
    headline: str,
    rows: list[tuple[str, str]],
) -> Panel:
    """Build a Rich Panel with a color-coded signal headline and key/value rows."""
    style = _SIGNAL_STYLE.get(signal, "dim")
    emoji = _SIGNAL_EMOJI.get(signal, "⚪")
    body_lines = [f"[{style}]{emoji} {headline}[/{style}]", ""]
    for label, value in rows:
        body_lines.append(f"  {label}: {value}")
    return Panel("\n".join(body_lines), title=f"[bold]{title}[/bold]", expand=True)


# ID: 27038966-d764-433e-b72d-591a460c0728
async def _query_dashboard_data(session: Any) -> dict[str, Any]:
    """Run all dashboard queries inside an open session. Returns raw data dict."""
    now = datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_60m = now - timedelta(minutes=60)
    cutoff_30m = now - timedelta(minutes=30)
    cutoff_10m = now - timedelta(minutes=10)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    data: dict[str, Any] = {}

    # --- Panel 1: Convergence Direction ---
    row = (
        await session.execute(
            text("""
            SELECT
                COUNT(*) FILTER (WHERE created_at >= :cutoff) AS created_24h,
                COUNT(*) FILTER (WHERE updated_at >= :cutoff AND status = 'resolved') AS resolved_24h,
                COUNT(*) FILTER (WHERE status = 'open' AND entry_type = 'finding') AS total_open
            FROM core.blackboard_entries
            WHERE entry_type = 'finding'
            """),
            {"cutoff": cutoff_24h},
        )
    ).fetchone()
    data["convergence"] = {
        "created": row.created_24h if row else 0,
        "resolved": row.resolved_24h if row else 0,
        "total_open": row.total_open if row else 0,
    }

    # --- Panel 2: Governor Inbox ---
    inbox_row = (
        await session.execute(
            text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE bb.status = 'indeterminate' AND bb.entry_type = 'finding'
                ) AS delegate_count,
                MIN(bb.created_at) FILTER (
                    WHERE bb.status = 'indeterminate' AND bb.entry_type = 'finding'
                ) AS oldest_delegate
            FROM core.blackboard_entries bb
            """),
        )
    ).fetchone()
    approval_row = (
        await session.execute(
            text("""
            SELECT
                COUNT(*) AS approval_count,
                MIN(created_at) AS oldest_approval
            FROM core.autonomous_proposals
            WHERE status = 'draft' AND approval_required = true
            """),
        )
    ).fetchone()
    delegate_count = inbox_row.delegate_count if inbox_row else 0
    oldest_delegate = inbox_row.oldest_delegate if inbox_row else None
    approval_count = approval_row.approval_count if approval_row else 0
    oldest_approval = approval_row.oldest_approval if approval_row else None
    data["inbox"] = {
        "delegate_count": delegate_count,
        "approval_count": approval_count,
        "total": delegate_count + approval_count,
        "oldest_delegate": oldest_delegate,
        "oldest_approval": oldest_approval,
        "cutoff_24h": cutoff_24h,
    }

    # --- Panel 3: Loop Running ---
    workers = (
        await session.execute(
            text("""
            SELECT worker_name, last_heartbeat
            FROM core.worker_registry
            WHERE status = 'active'
            ORDER BY last_heartbeat ASC NULLS FIRST
            """),
        )
    ).fetchall()
    stale_workers: list[tuple[str, str]] = []
    worst_age = "green"
    for w in workers:
        hb = w.last_heartbeat
        if hb is None:
            stale_workers.append((w.worker_name, "no heartbeat"))
            worst_age = "red"
            continue
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=UTC)
        if hb < cutoff_60m:
            stale_workers.append((w.worker_name, _age(hb)))
            worst_age = "red"
        elif hb < cutoff_10m:
            stale_workers.append((w.worker_name, _age(hb)))
            if worst_age != "red":
                worst_age = "amber"
    data["loop"] = {
        "active_count": len(workers),
        "stale_workers": stale_workers,
        "signal": worst_age,
    }

    # --- Panel 4: Pipeline Moving ---
    proposal_dist = (
        await session.execute(
            text("""
            SELECT status, COUNT(*) AS cnt
            FROM core.autonomous_proposals
            GROUP BY status
            ORDER BY cnt DESC
            """),
        )
    ).fetchall()
    executed_today = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.autonomous_proposals
            WHERE status = 'executed' AND execution_completed_at >= :today
            """),
            {"today": today_start},
        )
    ).fetchone()
    failed_count = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.autonomous_proposals
            WHERE status = 'failed'
            """),
        )
    ).fetchone()
    stuck_count = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.autonomous_proposals
            WHERE status = 'approved' AND approved_at < :cutoff
            """),
            {"cutoff": cutoff_30m},
        )
    ).fetchone()
    last_consequence = (
        await session.execute(
            text("""
            SELECT MAX(recorded_at) AS last_ts
            FROM core.proposal_consequences
            """),
        )
    ).fetchone()
    data["pipeline"] = {
        "distribution": {r.status: r.cnt for r in proposal_dist},
        "executed_today": executed_today.cnt if executed_today else 0,
        "failed": failed_count.cnt if failed_count else 0,
        "stuck_approved": stuck_count.cnt if stuck_count else 0,
        "last_consequence_ts": last_consequence.last_ts if last_consequence else None,
        "cutoff_60m": cutoff_60m,
    }

    # --- Panel 5: Autonomous Reach ---
    dry_run = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.blackboard_entries
            WHERE subject LIKE 'audit.remediation.dry_run%'
            AND status = 'open'
            """),
        )
    ).fetchone()
    abandoned = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.blackboard_entries
            WHERE entry_type = 'finding'
            AND status = 'abandoned'
            """),
        )
    ).fetchone()
    in_flight = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.blackboard_entries
            WHERE entry_type = 'finding'
            AND status = 'claimed'
            AND claimed_by = (
                SELECT worker_uuid FROM core.worker_registry
                WHERE worker_name = 'Violation Executor'
                AND status = 'active'
                LIMIT 1
            )
            """),
        )
    ).fetchone()
    data["reach"] = {
        "dry_run_candidates": dry_run.cnt if dry_run else 0,
        "abandoned": abandoned.cnt if abandoned else 0,
        "in_flight": in_flight.cnt if in_flight else 0,
    }

    return data


# ID: 178097be-03e6-4b27-90c9-2b76599f0d38
def _build_panels(data: dict[str, Any]) -> list[Panel]:
    """Translate raw query data into five Rich Panels with color signals."""
    panels: list[Panel] = []

    # --- Panel 1: Convergence Direction ---
    try:
        c = data["convergence"]
        created, resolved, total_open = c["created"], c["resolved"], c["total_open"]
        if resolved > created:
            signal = "green"
            direction = "converging"
        elif created > resolved:
            signal = "red"
            direction = "diverging"
        else:
            signal = "blue"
            direction = "stable"
        panels.append(
            _make_panel(
                "Convergence Direction",
                signal,
                f"Net direction: {direction}",
                [
                    ("Created (24h)", str(created)),
                    ("Resolved (24h)", str(resolved)),
                    ("Net", f"{resolved - created:+d}"),
                    ("Total open findings", str(total_open)),
                ],
            )
        )
    except Exception:
        panels.append(
            _make_panel("Convergence Direction", "grey", "UNKNOWN — query failed", [])
        )

    # --- Panel 2: Governor Inbox ---
    try:
        inbox = data["inbox"]
        total = inbox["total"]
        has_old = False
        for ts in (inbox["oldest_delegate"], inbox["oldest_approval"]):
            if ts is not None:
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                if ts < inbox["cutoff_24h"]:
                    has_old = True
        if total == 0:
            signal = "green"
        elif total <= 3 and not has_old:
            signal = "amber"
        else:
            signal = "red"
        panels.append(
            _make_panel(
                "Governor Inbox",
                signal,
                f"{total} item{'s' if total != 1 else ''} awaiting governor",
                [
                    ("Delegate (indeterminate)", str(inbox["delegate_count"])),
                    ("Approval required", str(inbox["approval_count"])),
                    ("Total", str(total)),
                ],
            )
        )
    except Exception:
        panels.append(
            _make_panel("Governor Inbox", "grey", "UNKNOWN — query failed", [])
        )

    # --- Panel 3: Loop Running ---
    try:
        loop = data["loop"]
        signal = loop["signal"]
        stale = loop["stale_workers"]
        active = loop["active_count"]
        if active == 0:
            signal = "red"
            headline = "No active workers"
        elif stale:
            names = ", ".join(f"{n} ({a})" for n, a in stale)
            headline = f"{active} active — stale: {names}"
        else:
            headline = f"{active} active — all heartbeats current"
        panels.append(
            _make_panel(
                "Loop Running",
                signal,
                headline,
                [("Active workers", str(active))]
                + [(f"Stale: {n}", a) for n, a in stale],
            )
        )
    except Exception:
        panels.append(_make_panel("Loop Running", "grey", "UNKNOWN — query failed", []))

    # --- Panel 4: Pipeline Moving ---
    try:
        p = data["pipeline"]
        dist = p["distribution"]
        executed_today = p["executed_today"]
        failed = p["failed"]
        stuck = p["stuck_approved"]
        last_ts = p["last_consequence_ts"]
        if failed > 0 or stuck > 0:
            signal = "red"
        elif executed_today > 0:
            if last_ts is not None:
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=UTC)
                if last_ts >= p["cutoff_60m"]:
                    signal = "green"
                else:
                    signal = "amber"
            else:
                signal = "green"
        else:
            signal = "amber"
        rows = [(s, str(n)) for s, n in dist.items()]
        rows.append(("Executed today", str(executed_today)))
        rows.append(("Failed", str(failed)))
        rows.append(("Stuck (approved > 30m)", str(stuck)))
        rows.append(("Last consequence", _age(p["last_consequence_ts"])))
        panels.append(
            _make_panel(
                "Pipeline Moving",
                signal,
                f"{executed_today} executed today, {failed} failed",
                rows,
            )
        )
    except Exception:
        panels.append(
            _make_panel("Pipeline Moving", "grey", "UNKNOWN — query failed", [])
        )

    # --- Panel 5: Autonomous Reach ---
    try:
        r = data["reach"]
        dry_run_candidates = r["dry_run_candidates"]
        abandoned = r["abandoned"]
        in_flight = r["in_flight"]
        if abandoned > 0:
            signal = "red"
            headline = (
                f"{abandoned} finding{'s' if abandoned != 1 else ''} "
                "abandoned — daemon cannot self-heal"
            )
        elif dry_run_candidates > 0:
            signal = "amber"
            headline = (
                f"{dry_run_candidates} graduation candidate{'s' if dry_run_candidates != 1 else ''} "
                "waiting"
            )
        else:
            signal = "green"
            headline = "Full autonomous reach — no blocked findings"
        rows: list[tuple[str, str]] = [
            ("Dry-run candidates (ready to graduate)", str(dry_run_candidates)),
            ("Currently on ViolationExecutor path", str(in_flight)),
            ("Abandoned (no path forward)", str(abandoned)),
        ]
        panels.append(_make_panel("Autonomous Reach", signal, headline, rows))
    except Exception:
        panels.append(
            _make_panel("Autonomous Reach", "grey", "UNKNOWN — query failed", [])
        )

    return panels


@runtime_app.command("dashboard")
@async_command
# ID: e570aefa-1103-4edc-921a-47d7dc97b5fb
async def dashboard_cmd(
    plain: bool = typer.Option(
        False, "--plain", help="Plain text output (log/pipe friendly)."
    ),
) -> None:
    """
    Five-panel governor dashboard for the CORE runtime.

    Shows convergence direction, governor inbox, loop health,
    pipeline status, and governance coverage — all read-only.
    """
    async with get_session() as session:
        data = await _query_dashboard_data(session)

    if plain:
        _render_dashboard_plain(data)
    else:
        _render_dashboard_rich(data)


# ID: c1a3d7e2-5f89-4b6c-a0d1-9e8f7c6b5a43
def _render_dashboard_rich(data: dict[str, Any]) -> None:
    panels = _build_panels(data)
    console.rule("[bold cyan]CORE Governor Dashboard[/bold cyan]")
    console.print(panels[0])
    console.print(Columns([panels[1], panels[2]], expand=True))
    console.print(Columns([panels[3], panels[4]], expand=True))
    console.rule()


# ID: d2b4e8f3-6a90-4c7d-b1e2-0f9a8d7c6b54
def _render_dashboard_plain(data: dict[str, Any]) -> None:
    logger.info("=== CORE Governor Dashboard ===\n")

    # Panel 1: Convergence
    try:
        c = data["convergence"]
        created, resolved = c["created"], c["resolved"]
        if resolved > created:
            direction = "converging"
        elif created > resolved:
            direction = "diverging"
        else:
            direction = "stable"
        logger.info("-- Convergence Direction --")
        logger.info("  created_24h:  %s", created)
        logger.info("  resolved_24h: %s", resolved)
        logger.info("  direction:    %s", direction)
        logger.info("  total_open:   %s", c["total_open"])
    except Exception:
        logger.info("-- Convergence Direction: UNKNOWN --")

    # Panel 2: Inbox
    try:
        inbox = data["inbox"]
        logger.info("\n-- Governor Inbox --")
        logger.info("  delegate:  %s", inbox["delegate_count"])
        logger.info("  approval:  %s", inbox["approval_count"])
        logger.info("  total:     %s", inbox["total"])
    except Exception:
        logger.info("\n-- Governor Inbox: UNKNOWN --")

    # Panel 3: Loop
    try:
        loop = data["loop"]
        logger.info("\n-- Loop Running --")
        logger.info("  active_workers: %s", loop["active_count"])
        for name, age_str in loop["stale_workers"]:
            logger.info("  stale: %s (%s)", name, age_str)
    except Exception:
        logger.info("\n-- Loop Running: UNKNOWN --")

    # Panel 4: Pipeline
    try:
        p = data["pipeline"]
        logger.info("\n-- Pipeline Moving --")
        for status, cnt in p["distribution"].items():
            logger.info("  %s %s", status.ljust(16), cnt)
        logger.info("  executed_today:    %s", p["executed_today"])
        logger.info("  failed:            %s", p["failed"])
        logger.info("  stuck_approved:    %s", p["stuck_approved"])
        logger.info("  last_consequence:  %s", _age(p["last_consequence_ts"]))
    except Exception:
        logger.info("\n-- Pipeline Moving: UNKNOWN --")

    # Panel 5: Autonomous Reach
    try:
        r = data["reach"]
        logger.info("\n-- Autonomous Reach --")
        logger.info("  dry_run_candidates: %s", r["dry_run_candidates"])
        logger.info("  in_flight:          %s", r["in_flight"])
        logger.info("  abandoned:          %s", r["abandoned"])
    except Exception:
        logger.info("\n-- Autonomous Reach: UNKNOWN --")
