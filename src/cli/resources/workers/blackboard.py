# src/cli/resources/workers/blackboard.py
"""Blackboard inspection command — read-only view of the worker coordination ledger."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from shared.cli_utils.decorators import core_command
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from .run import workers_app


logger = getLogger(__name__)
console = Console()


@workers_app.command("blackboard")
@core_command(dangerous=False)
# ID: 4a064a13-ac50-45be-aba5-dc9ce99540b6
async def workers_blackboard_cmd(
    ctx: typer.Context,
    filter: str | None = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter by subject prefix (e.g. 'ai.prompt.model_required').",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: open | claimed | resolved | abandoned.",
    ),
    entry_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by entry_type: finding | report | heartbeat | claim | proposal.",
    ),
    limit: int = typer.Option(
        50, "--limit", "-n", help="Maximum number of entries to display."
    ),
    show_payload: bool = typer.Option(
        False, "--payload", "-p", help="Show full JSON payload for each entry."
    ),
) -> None:
    """Inspect the constitutional worker blackboard (read-only)."""
    from sqlalchemy import text

    clauses = ["1=1"]
    params: dict[str, object] = {}
    if filter:
        clauses.append("subject LIKE :subject_prefix")
        params["subject_prefix"] = f"{filter}%"
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if entry_type:
        clauses.append("entry_type = :entry_type")
        params["entry_type"] = entry_type
    where = " AND ".join(clauses)
    query = text(
        f"\n        SELECT id, entry_type, status, subject, worker_uuid, created_at, payload\n        FROM core.blackboard_entries\n        WHERE {where}\n        ORDER BY created_at DESC\n        LIMIT :limit\n        "
    )
    params["limit"] = limit
    async with get_session() as session:
        result = await session.execute(query, params)
        rows = result.fetchall()
    if not rows:
        logger.info("[yellow]No blackboard entries found.[/yellow]")
        raise typer.Exit()
    table = Table(
        title=f"Blackboard — {len(rows)} entr{('y' if len(rows) == 1 else 'ies')}",
        show_lines=show_payload,
    )
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Subject")
    table.add_column("Worker UUID", style="dim", no_wrap=True)
    table.add_column("Created", style="dim", no_wrap=True)
    if show_payload:
        table.add_column("Payload")
    _STATUS_STYLE = {
        "open": "green",
        "claimed": "yellow",
        "resolved": "blue",
        "abandoned": "red",
        "indeterminate": "magenta",
        "dry_run_complete": "cyan",
    }
    for row in rows:
        _entry_id, etype, estatus, subject, worker_uuid, created_at, payload = row
        status_style = _STATUS_STYLE.get(estatus, "white")
        status_str = f"[{status_style}]{estatus}[/{status_style}]"
        created_str = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
        worker_str = str(worker_uuid)[:8] + "..." if worker_uuid else "-"
        row_cells = [etype, status_str, subject, worker_str, created_str]
        if show_payload:
            raw = payload if isinstance(payload, dict) else json.loads(payload or "{}")
            row_cells.append(json.dumps(raw, indent=2))
        table.add_row(*row_cells)
    logger.info(table)
