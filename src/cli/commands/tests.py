# src/cli/commands/tests.py
"""Test maturity dashboard — single-glance view of CORE's autonomous test
generation health.

Shows:
  - Worker liveness (test_coverage_sensor, test_runner_sensor, test_remediator)
  - Proposal pipeline counts by status (last 30 days)
  - Top failure reasons
  - Open coverage gaps (files the sensor has flagged but no test exists yet)
  - Recent successful completions

Constitutional Alignment:
  - Read-only; no mutation surface.
  - Direct DB access is permitted in CLI (architecture.api.no_direct_database_access
    applies to src/api/, not src/cli/).
  - Rich rendering stays in this CLI layer; no Rich in shared/body/mind/will.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

from cli.utils import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

tests_app = typer.Typer(
    help="Test maturity dashboard and autonomous generation insights.",
    no_args_is_help=True,
)

_TEST_WORKERS = ("test_coverage_sensor", "test_runner_sensor", "test_remediator")
_DAYS = 30


# ID: b4ea3a5e-5f6d-4164-af59-52280de58aa6
def _liveness_color(minutes_ago: float | None) -> str:
    if minutes_ago is None:
        return "red"
    if minutes_ago < 10:
        return "green"
    if minutes_ago < 60:
        return "yellow"
    return "red"


@tests_app.command("status")
@core_command(dangerous=False, requires_context=False)
# ID: 69e6d3d3-5aba-4c6e-8127-54adab4c27d0
async def tests_status(
    ctx: typer.Context,
    days: int = typer.Option(
        _DAYS, "--days", "-d", help="Lookback window for proposal stats (default 30)"
    ),
    gaps: int = typer.Option(
        20, "--gaps", "-g", help="Max coverage gaps to show (default 20)"
    ),
) -> None:
    """Single-glance test maturity: sensor health, pipeline stats, coverage gaps."""
    _ = ctx

    async with get_session() as session:
        # ── 1. Worker liveness ──────────────────────────────────────────────
        worker_rows = (
            await session.execute(
                text(
                    """
                    SELECT declaration_name,
                           last_heartbeat,
                           EXTRACT(EPOCH FROM (now() - last_heartbeat)) / 60
                               AS minutes_ago
                    FROM core.worker_registry
                    WHERE declaration_name = ANY(:names)
                    ORDER BY declaration_name
                    """
                ),
                {"names": list(_TEST_WORKERS)},
            )
        ).fetchall()

        # ── 2. Proposal pipeline counts ─────────────────────────────────────
        pipeline_rows = (
            await session.execute(
                text(
                    """
                    SELECT status, count(*) AS n
                    FROM core.autonomous_proposals
                    WHERE (goal ILIKE '%test%' OR goal ILIKE '%build.tests%')
                      AND created_at > now() - (:days * interval '1 day')
                    GROUP BY status
                    ORDER BY status
                    """
                ),
                {"days": days},
            )
        ).fetchall()

        # ── 3. Failure reasons ───────────────────────────────────────────────
        failure_rows = (
            await session.execute(
                text(
                    """
                    SELECT left(coalesce(failure_reason, '(no reason)'), 72) AS reason,
                           count(*) AS n
                    FROM core.autonomous_proposals
                    WHERE (goal ILIKE '%test%' OR goal ILIKE '%build.tests%')
                      AND status = 'failed'
                      AND created_at > now() - (:days * interval '1 day')
                    GROUP BY 1
                    ORDER BY n DESC
                    LIMIT 6
                    """
                ),
                {"days": days},
            )
        ).fetchall()

        # ── 4. Open coverage gaps ────────────────────────────────────────────
        gap_rows = (
            await session.execute(
                text(
                    """
                    SELECT be.subject, be.created_at
                    FROM core.blackboard_entries be
                    JOIN core.worker_registry wr
                         ON wr.worker_uuid = be.worker_uuid
                    WHERE wr.declaration_name = 'test_coverage_sensor'
                      AND be.status = 'open'
                      AND be.subject NOT LIKE '%run.complete%'
                      AND be.subject NOT LIKE '%heartbeat%'
                    ORDER BY be.created_at DESC
                    LIMIT :gaps
                    """
                ),
                {"gaps": gaps},
            )
        ).fetchall()

        # ── 5. Recent completions (last 7 days) ─────────────────────────────
        recent_rows = (
            await session.execute(
                text(
                    """
                    SELECT left(goal, 70) AS goal, created_at
                    FROM core.autonomous_proposals
                    WHERE (goal ILIKE '%test%' OR goal ILIKE '%build.tests%')
                      AND status = 'completed'
                      AND created_at > now() - interval '7 days'
                    ORDER BY created_at DESC
                    LIMIT 8
                    """
                ),
            )
        ).fetchall()

    # ── Render ───────────────────────────────────────────────────────────────

    # Workers
    w_table = Table(box=None, show_header=True, header_style="bold")
    w_table.add_column("Worker")
    w_table.add_column("Last heartbeat", justify="right")
    w_table.add_column("Ago", justify="right")

    seen = {r[0] for r in worker_rows}
    for row in worker_rows:
        name, hb, mins = row
        color = _liveness_color(float(mins) if mins is not None else None)
        ago = (
            f"[{color}]{float(mins):.0f}m[/{color}]"
            if mins is not None
            else "[red]never[/red]"
        )
        w_table.add_row(name, str(hb)[:19] if hb else "—", ago)
    for missing in sorted(set(_TEST_WORKERS) - seen):
        w_table.add_row(missing, "—", "[red]not registered[/red]")

    console.print(
        Panel(w_table, title="[bold]Worker Liveness[/bold]", border_style="blue")
    )

    # Pipeline
    total = sum(r[1] for r in pipeline_rows)
    completed = next((r[1] for r in pipeline_rows if r[0] == "completed"), 0)
    failed = next((r[1] for r in pipeline_rows if r[0] == "failed"), 0)
    pass_rate = f"{completed / total * 100:.0f}%" if total else "—"
    fail_rate = f"{failed / total * 100:.0f}%" if total else "—"

    p_table = Table(box=None, show_header=True, header_style="bold")
    p_table.add_column("Status")
    p_table.add_column("Count", justify="right")
    p_table.add_column("Share", justify="right")
    for row in pipeline_rows:
        status, n = row
        color = {
            "completed": "green",
            "failed": "red",
            "executing": "yellow",
            "draft": "dim",
            "rejected": "magenta",
        }.get(status, "white")
        p_table.add_row(
            f"[{color}]{status}[/{color}]",
            str(n),
            f"{n / total * 100:.0f}%" if total else "—",
        )
    p_table.add_row("", "", "")
    p_table.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total}[/bold]",
        f"pass {pass_rate}  fail {fail_rate}",
    )

    console.print(
        Panel(
            p_table,
            title=f"[bold]Proposal Pipeline — last {days}d[/bold]",
            border_style="blue",
        )
    )

    # Failures
    if failure_rows:
        f_table = Table(box=None, show_header=True, header_style="bold")
        f_table.add_column("Failure reason")
        f_table.add_column("Count", justify="right")
        for row in failure_rows:
            reason, n = row
            f_table.add_row(str(reason), str(n))
        console.print(
            Panel(f_table, title="[bold]Top Failure Reasons[/bold]", border_style="red")
        )

    # Coverage gaps
    if gap_rows:
        g_table = Table(box=None, show_header=True, header_style="bold")
        g_table.add_column("File (coverage gap)")
        g_table.add_column("Flagged", justify="right")
        for row in gap_rows:
            subject, flagged_at = row
            # strip leading "python::test.coverage::" prefix if present
            label = subject.replace("python::test.coverage::", "")
            g_table.add_row(label, str(flagged_at)[:16] if flagged_at else "—")
        console.print(
            Panel(
                g_table,
                title=f"[bold]Open Coverage Gaps ({len(gap_rows)} shown)[/bold]",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                "[green]No open coverage gaps[/green]",
                title="[bold]Coverage Gaps[/bold]",
                border_style="green",
            )
        )

    # Recent successes
    if recent_rows:
        r_table = Table(box=None, show_header=True, header_style="bold")
        r_table.add_column("Goal")
        r_table.add_column("Completed", justify="right")
        for row in recent_rows:
            goal_text, completed_at = row
            r_table.add_row(
                str(goal_text), str(completed_at)[:16] if completed_at else "—"
            )
        console.print(
            Panel(
                r_table,
                title="[bold]Recent Completions — last 7d[/bold]",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[dim]No completions in the last 7 days[/dim]",
                title="[bold]Recent Completions[/bold]",
                border_style="dim",
            )
        )
