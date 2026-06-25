# src/cli/resources/workers/blackboard.py
"""Blackboard inspection and maintenance commands for the worker coordination ledger."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from cli.utils.decorators import core_command
from shared.infrastructure.database.session_manager import get_session

from .run import workers_app


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
        params["subject_prefix"] = f"%{filter}%"
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
        console.print("[yellow]No blackboard entries found.[/yellow]")
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
    console.print(table)


@workers_app.command("purge")
@core_command(dangerous=True)
# ID: b2b41188-284f-47e7-8524-1a3027955755
async def workers_blackboard_purge_cmd(
    ctx: typer.Context,
    status: str = typer.Option(
        ...,
        "--status",
        "-s",
        help=(
            "Filter by status (required): open | claimed | resolved | abandoned | "
            "indeterminate | dry_run_complete | deferred_to_proposal | awaiting_reaudit | "
            "suppressed."
        ),
    ),
    rule: str | None = typer.Option(
        None,
        "--rule",
        "-r",
        help="Filter by rule ID prefix in subject (e.g. 'style.import_order').",
    ),
    before: int | None = typer.Option(
        None,
        "--before",
        "-b",
        help="Only purge entries older than this many hours.",
    ),
    write: bool = typer.Option(
        False, "--write", "-w", help="Apply deletion. Dry-run by default."
    ),
) -> None:
    """Purge blackboard entries by status, with optional rule and age filters."""
    from sqlalchemy import text

    clauses = ["status = :status"]
    params: dict[str, object] = {"status": status}
    if rule:
        clauses.append("subject LIKE :subject_prefix")
        params["subject_prefix"] = f"{rule}%"
    if before is not None:
        clauses.append("created_at < NOW() - MAKE_INTERVAL(hours => :hours)")
        params["hours"] = before
    where = " AND ".join(clauses)

    preview_query = text(
        f"""
        SELECT id, entry_type, status, subject, worker_uuid, created_at
        FROM core.blackboard_entries
        WHERE {where}
        ORDER BY created_at DESC
        """
    )
    delete_query = text(
        f"""
        DELETE FROM core.blackboard_entries
        WHERE {where}
        """
    )

    _STATUS_STYLE = {
        "open": "green",
        "claimed": "yellow",
        "resolved": "blue",
        "abandoned": "red",
        "indeterminate": "magenta",
        "dry_run_complete": "cyan",
    }

    # Single session spans preview and delete — prevents TOCTOU between them.
    async with get_session() as session:
        result = await session.execute(preview_query, params)
        rows = result.fetchall()

        if not rows:
            console.print(
                "[yellow]No blackboard entries match the given filters.[/yellow]"
            )
            raise typer.Exit()

        table = Table(
            title=f"Purge preview — {len(rows)} entr{('y' if len(rows) == 1 else 'ies')}",
        )
        table.add_column("Type", style="cyan", no_wrap=True)
        table.add_column("Status", no_wrap=True)
        table.add_column("Subject")
        table.add_column("Worker UUID", style="dim", no_wrap=True)
        table.add_column("Created", style="dim", no_wrap=True)

        for row in rows:
            _entry_id, etype, estatus, subject, worker_uuid, created_at = row
            status_style = _STATUS_STYLE.get(estatus, "white")
            status_str = f"[{status_style}]{estatus}[/{status_style}]"
            created_str = (
                created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "-"
            )
            worker_str = str(worker_uuid)[:8] + "..." if worker_uuid else "-"
            table.add_row(etype, status_str, subject, worker_str, created_str)
        console.print(table)

        if not write:
            console.print(
                f"\n[dim]Dry run:[/dim] {len(rows)} entries would be deleted. "
                "Pass [bold]--write[/bold] to apply."
            )
            return

        result = await session.execute(delete_query, params)
        await session.commit()
        deleted = result.rowcount

    console.print(f"\n[bold green]Purged {deleted} blackboard entries.[/bold green]")


@workers_app.command("resolve")
@core_command(dangerous=False)
# ID: 0dcd5509-ff34-42aa-b866-de1d76c242ae
async def workers_blackboard_resolve_cmd(
    ctx: typer.Context,
    entry_id: str = typer.Argument(..., help="Blackboard entry UUID."),
    reason: str = typer.Option(
        ..., "--reason", "-r", help="Why this finding is being closed."
    ),
    by: str = typer.Option("cli_admin", "--by", help="Operator identity."),
    authority: str = typer.Option(
        "human.cli_operator",
        "--authority",
        help="Authority under which the resolution is recorded (URS NFR.5).",
    ),
) -> None:
    """
    Close an indeterminate blackboard finding with an operator-provided reason.

    Symmetric counterpart to 'proposals reject' for findings the audit sensor
    delegated to the governor. Flips status to 'resolved', stamps the
    operator attribution into payload, and stops counting against the
    Governor Inbox.
    """
    from body.services.blackboard_service.blackboard_service import BlackboardService

    updated = await BlackboardService().resolve_indeterminate_entry(
        entry_id=entry_id,
        reason=reason,
        resolved_by=by,
        resolution_authority=authority,
    )
    if updated == 0:
        console.print(
            f"[yellow]No change: entry {entry_id} is not in 'indeterminate' "
            "status or does not exist.[/yellow]"
        )
        raise typer.Exit(1)
    console.print(
        f"[green]✅ Finding {entry_id} RESOLVED by {by} under {authority}.[/green]"
    )
