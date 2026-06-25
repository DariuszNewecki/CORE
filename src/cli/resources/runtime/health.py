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

from body.services.health_log_service import F19_CONVERGENCE_SQL, GOVERNOR_INBOX_SQL
from cli.utils import async_command
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.schedule import load_worker_schedule_state


logger = getLogger(__name__)
console = Console()

_CFG_H = load_operational_config().health
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


def _worker_colour(
    last_heartbeat: datetime | None, is_active_declared: bool = True
) -> str:
    """Liveness colour derived from heartbeat age. Per ADR-020,
    last_heartbeat is the canonical liveness signal.

    Workers whose declaration is not status=active (paused, deprecated,
    or orphan rows whose YAML was removed) are rendered dim — they are
    not expected to heartbeat, so heartbeat age is irrelevant.
    """
    if not is_active_declared:
        return "dim"
    if last_heartbeat is None:
        return "yellow"
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=UTC)
    age_s = (datetime.now(UTC) - last_heartbeat).total_seconds()
    if age_s < _CFG_H.worker_alive_threshold_sec:
        return "green"
    if age_s < _CFG_H.worker_warn_threshold_sec:
        return "yellow"
    return "red"


def _liveness_label(
    last_heartbeat: datetime | None, is_active_declared: bool = True
) -> str:
    """Liveness label derived from heartbeat freshness. Per ADR-020,
    a worker is alive iff its last heartbeat is within the silent-worker
    threshold (10 minutes, matching health_log_service.silent_workers).

    Workers whose declaration is not status=active are labelled
    ``inactive`` regardless of heartbeat age — heartbeat staleness is
    expected and not a fault signal.
    """
    if not is_active_declared:
        return "inactive"
    if last_heartbeat is None:
        return "stale"
    if last_heartbeat.tzinfo is None:
        last_heartbeat = last_heartbeat.replace(tzinfo=UTC)
    age_s = (datetime.now(UTC) - last_heartbeat).total_seconds()
    if age_s >= _CFG_H.worker_alive_threshold_sec:
        return "stale"
    return "alive"


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
    schedule_state = load_worker_schedule_state()
    active_uuids = schedule_state.active_uuids

    async with get_session() as session:
        workers = (
            await session.execute(
                text(
                    "\n            SELECT worker_name, worker_uuid, worker_class, phase, last_heartbeat\n            FROM core.worker_registry\n            ORDER BY last_heartbeat DESC NULLS LAST\n            "
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
        try:
            blast = (
                await session.execute(
                    text(
                        "\n            SELECT symbol_path, affected_symbol_count, direct_caller_count\n            FROM core.v_symbol_blast_radius\n            ORDER BY affected_symbol_count DESC\n            LIMIT 10\n            "
                    )
                )
            ).fetchall()
        except Exception:
            blast = []
    if plain:
        _render_plain(
            workers, bb_summary, bb_recent, health, crawl, blast, active_uuids
        )
    else:
        _render_rich(workers, bb_summary, bb_recent, health, crawl, blast, active_uuids)


def _render_rich(
    workers,
    bb_summary,
    bb_recent,
    health,
    crawl,
    blast,
    active_uuids: frozenset[str],
) -> None:
    console.rule("[bold cyan]CORE Runtime Health[/bold cyan]")
    console.print("\n[bold]Workers[/bold]")
    t = Table(show_header=True, header_style="bold magenta")
    t.add_column("Name")
    t.add_column("Class")
    t.add_column("Phase")
    t.add_column("Liveness")
    t.add_column("Last Heartbeat")
    for w in workers:
        is_active = str(w.worker_uuid) in active_uuids
        c = _worker_colour(w.last_heartbeat, is_active)
        label = _liveness_label(w.last_heartbeat, is_active)
        t.add_row(
            w.worker_name,
            w.worker_class,
            w.phase,
            f"[{c}]{label}[/{c}]",
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


def _render_plain(
    workers,
    bb_summary,
    bb_recent,
    health,
    crawl,
    blast,
    active_uuids: frozenset[str],
) -> None:
    logger.info("=== CORE Runtime Health ===\n")
    logger.info("-- Workers --")
    for w in workers:
        is_active = str(w.worker_uuid) in active_uuids
        label = _liveness_label(w.last_heartbeat, is_active)
        logger.info(
            "  %s %s %s",
            w.worker_name.ljust(30),
            label.ljust(10),
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
async def _query_dashboard_data(session: Any, schedule_state: Any) -> dict[str, Any]:
    """Run all dashboard queries inside an open session. Returns raw data dict."""
    now = datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=_CFG_H.long_lookback_hours)
    cutoff_60m = now - timedelta(minutes=_CFG_H.medium_lookback_minutes)
    cutoff_30m = now - timedelta(minutes=_CFG_H.short_lookback_minutes)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    data: dict[str, Any] = {}

    # --- Panel 1: Convergence Direction ---
    # F-19 honest convergence (#563). The CTE lives in
    # `body.services.health_log_service.F19_CONVERGENCE_SQL` as the single
    # source of truth — also used by `ObserverWorker` to persist the same
    # counts into `core.system_health_log.payload` so the live dashboard and
    # the 30-day time series agree.
    row = (
        await session.execute(
            text(F19_CONVERGENCE_SQL),
            {"cutoff": cutoff_24h},
        )
    ).fetchone()

    # Trajectory metric (#261): compare current open_findings against the
    # value from ~6 hours ago using the existing system_health_log series.
    # Backlog-trend, not flow-noise — converges/diverges if the open set
    # is shrinking/growing across the window.
    trajectory_lookback_hours = 6
    log_count_row = (
        await session.execute(
            text("SELECT COUNT(*) AS cnt FROM core.system_health_log"),
        )
    ).fetchone()
    log_count = log_count_row.cnt if log_count_row else 0

    trajectory: dict[str, Any]
    if log_count >= 2:
        current_row = (
            await session.execute(
                text("""
                SELECT observed_at, open_findings
                FROM core.system_health_log
                ORDER BY observed_at DESC
                LIMIT 1
                """),
            )
        ).fetchone()
        # Exclude current_row so prior_row cannot resolve to the same snapshot.
        # Without the WHERE guard, a sparse log where the most-recent entry is
        # also closest to the lookback target produces delta=0 and a false
        # "stable" direction.
        prior_row = (
            await session.execute(
                text("""
                SELECT observed_at, open_findings
                FROM core.system_health_log
                WHERE observed_at < :current_ts
                ORDER BY ABS(
                    EXTRACT(EPOCH FROM (
                        observed_at - (now() - make_interval(hours => :hours))
                    ))
                )
                LIMIT 1
                """),
                {
                    "hours": trajectory_lookback_hours,
                    "current_ts": current_row.observed_at,
                },
            )
        ).fetchone()
        current_open = current_row.open_findings
        if prior_row is None:
            # Only one distinct snapshot exists — cannot compute a meaningful delta.
            trajectory = {
                "current": current_open,
                "prior": None,
                "delta": None,
                "lookback_hours": trajectory_lookback_hours,
                "direction": "insufficient-data",
            }
        else:
            prior_open = prior_row.open_findings
            delta = current_open - prior_open
            if delta < 0:
                direction = "converging"
            elif delta > 0:
                direction = "diverging"
            else:
                direction = "stable"
            trajectory = {
                "current": current_open,
                "prior": prior_open,
                "delta": delta,
                "lookback_hours": trajectory_lookback_hours,
                "direction": direction,
            }
    else:
        # 0 or 1 rows in the health log — no usable backlog comparison yet.
        trajectory = {
            "current": None,
            "prior": None,
            "delta": None,
            "lookback_hours": trajectory_lookback_hours,
            "direction": "insufficient-data",
        }

    created = row.created_24h if row else 0
    resolved = row.resolved_24h if row else 0
    stuck = row.stuck_24h if row else 0
    # Finding #6 (#563): when nothing flowed in or out, the system is frozen,
    # not stable. Override trajectory to "frozen" when 24h flow is zero,
    # regardless of whether history is sufficient to compute a direction —
    # zero flow is a flow-only criterion, independent of backlog comparison.
    flow_zero = created == 0 and resolved == 0 and stuck == 0
    if flow_zero and trajectory["direction"] in ("stable", "insufficient-data"):
        trajectory["direction"] = "frozen"
    data["convergence"] = {
        "created": created,
        "resolved": resolved,
        "stuck": stuck,
        "total_open": row.total_open if row else 0,
        "trajectory": trajectory,
    }

    # --- Panel 2: Governor Inbox ---
    # Reads GOVERNOR_INBOX_SQL — the SAME predicate ObserverWorker persists as the
    # F-19 governor-inbox backlog component (#563), so the dashboard number and the
    # convergence operand cannot drift. Distinct `indeterminate`+`human` subjects
    # (was: a raw row count over any-mechanism indeterminate findings).
    inbox_row = (await session.execute(text(GOVERNOR_INBOX_SQL))).fetchone()
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
    delegate_count = inbox_row.governor_inbox if inbox_row else 0
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

    # --- Panel 3: Loop Running (ADR-041 D2/D3/D5) ---
    # Per-worker thresholds + orphan-skip from the shared loader. Binary
    # stale/alive: amber tier dropped (ADR-041 D5) because it had no
    # semantic basis under per-worker thresholds.
    # Uses the caller-supplied session to avoid opening a second DB connection
    # concurrently (the WorkerRegistryService pattern is for standalone callers).
    _worker_rows = (
        await session.execute(
            text("""
                SELECT
                    worker_uuid,
                    worker_name,
                    last_heartbeat,
                    EXTRACT(EPOCH FROM (now() - last_heartbeat))::int AS seconds_silent
                FROM core.worker_registry
                ORDER BY seconds_silent DESC NULLS LAST
            """)
        )
    ).fetchall()
    stale_workers: list[tuple[str, str]] = []
    for _wr in _worker_rows:
        if str(_wr.worker_uuid) not in schedule_state.active_uuids:
            continue
        seconds_silent = _wr.seconds_silent or 0
        threshold = schedule_state.thresholds.get(
            str(_wr.worker_uuid), schedule_state.fallback_sec
        )
        if seconds_silent > threshold:
            stale_workers.append((_wr.worker_name, _age(_wr.last_heartbeat)))
    data["loop"] = {
        # Active count = declared active workers (ADR-041 D3 orphan-skip
        # applied). Previously this counted every worker_registry row
        # including orphans, which overstated the live worker count.
        "active_count": len(schedule_state.active_uuids),
        "stale_workers": stale_workers,
        "signal": "red" if stale_workers else "green",
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
            WHERE status = 'completed' AND execution_completed_at >= :today
            """),
            {"today": today_start},
        )
    ).fetchone()
    failed_today = (
        await session.execute(
            text("""
            SELECT COUNT(*) AS cnt
            FROM core.autonomous_proposals
            WHERE status = 'failed' AND execution_completed_at >= :today
            """),
            {"today": today_start},
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
        "failed_today": failed_today.cnt if failed_today else 0,
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
    # Panel 4 honesty fix (2026-06-06, #563 honesty defect class): exclude
    # Type A sensor-by-design audit trail from the "no path forward" headline.
    # Classification mirrors Panel 1's CASE block above — keep the two in sync.
    # Pre-fix: this query returned 8,764 (8,437 loop_hold.sample::* +
    #          327 *.scope_collision::* + Type B); the "daemon cannot
    #          self-heal" framing was wrong for Type A.
    #
    # Count DISTINCT subject, not rows (2026-06-16): a finding the daemon cannot
    # heal is re-abandoned every cycle, so COUNT(*) amplified the headline ~15x
    # (389 rows = 26 distinct findings). The governor acts on a subject, not each
    # recycled abandonment — mirrors health_log_service.governor_inbox.
    abandoned = (
        await session.execute(
            text("""
            SELECT COUNT(DISTINCT subject) AS cnt
            FROM core.blackboard_entries
            WHERE entry_type = 'finding'
            AND status = 'abandoned'
            AND subject NOT LIKE 'worker.silent::%'
            AND subject <> 'worker.error'
            AND subject NOT LIKE '%.cycle_error'
            AND subject NOT LIKE '%.scope_collision::%'
            AND subject NOT LIKE 'loop_hold.sample::%'
            AND subject <> 'coherence.violation_executor.blast_bound'
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
    # Backlog-trend metric: compares current total open findings against the
    # value from ~lookback_hours ago in the system_health_log series.
    # Shrinking open set = converging; growing = diverging; unchanged = stable.
    try:
        traj = data["convergence"]["trajectory"]
        direction = traj["direction"]
        current = traj["current"]
        prior = traj["prior"]
        delta = traj["delta"]
        lookback = traj["lookback_hours"]

        direction_meta = {
            "converging": ("green", "Converging ↓"),
            "diverging": ("red", "Diverging ↑"),
            "stable": ("amber", "Stable →"),
            "frozen": ("red", "Frozen ⏸ — no flow in 24h"),
            "insufficient-data": ("grey", "Insufficient data"),
        }
        signal, headline = direction_meta.get(direction, ("grey", "Insufficient data"))

        conv = data["convergence"]
        panels.append(
            _make_panel(
                "Convergence Direction",
                signal,
                headline,
                [
                    ("Open now", str(current) if current is not None else "—"),
                    (
                        f"Open {lookback}h ago",
                        str(prior) if prior is not None else "—",
                    ),
                    ("Delta", f"{delta:+d}" if delta is not None else "—"),
                    ("Created 24h (subjects)", str(conv["created"])),
                    ("Resolved 24h (subjects)", str(conv["resolved"])),
                    ("Stuck 24h (Type B abandoned)", str(conv["stuck"])),
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
        failed_today = p["failed_today"]
        stuck = p["stuck_approved"]
        last_ts = p["last_consequence_ts"]
        if failed_today > 0 or stuck > 0:
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
                # Proposals completed today but no consequence row ever recorded —
                # consequence-recording pipeline integrity is unclear.
                signal = "amber"
        else:
            signal = "amber"
        rows = [(s, str(n)) for s, n in dist.items()]
        rows.append(("Executed today", str(executed_today)))
        rows.append(("Failed today", str(failed_today)))
        rows.append(("Stuck (approved > 30m)", str(stuck)))
        rows.append(("Last consequence", _age(p["last_consequence_ts"])))
        panels.append(
            _make_panel(
                "Pipeline Moving",
                signal,
                f"{executed_today} executed today, {failed_today} failed today",
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
    schedule_state = load_worker_schedule_state()
    async with get_session() as session:
        data = await _query_dashboard_data(session, schedule_state)

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

    # Panel 1: Convergence — backlog trajectory over the lookback window.
    try:
        conv = data["convergence"]
        traj = conv["trajectory"]
        direction_label = {
            "converging": "Converging (↓)",
            "diverging": "Diverging (↑)",
            "stable": "Stable (→)",
            "frozen": "Frozen (⏸) — no flow in 24h",
            "insufficient-data": "Insufficient data",
        }.get(traj["direction"], "Insufficient data")

        current = traj["current"]
        prior = traj["prior"]
        delta = traj["delta"]
        lookback = traj["lookback_hours"]

        logger.info("-- Convergence Direction --")
        logger.info("  direction:        %s", direction_label)
        logger.info(
            "  open_now:         %s", str(current) if current is not None else "—"
        )
        logger.info(
            "  open_%dh_ago:      %s",
            lookback,
            str(prior) if prior is not None else "—",
        )
        logger.info(
            "  delta:            %s",
            f"{delta:+d}" if delta is not None else "—",
        )
        logger.info("  created_24h:      %s (distinct subjects)", conv["created"])
        logger.info("  resolved_24h:     %s (distinct subjects)", conv["resolved"])
        logger.info("  stuck_24h:        %s (Type B abandoned)", conv["stuck"])
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
        logger.info("  failed_today:      %s", p["failed_today"])
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
