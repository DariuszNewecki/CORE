# src/cli/commands/inspect/refusals.py
"""Constitutional refusal inspection commands.

Thin clients over /v1/refusals and /v1/refusals/stats (ADR-057 D3).
Default limits are hardcoded CLI options now — they were previously read
from `shared.infrastructure.intent.operational_config.load_operational_config`,
which is a `shared.*` reach across the CLI boundary.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import CommandBehavior, CommandLayer, command_meta


logger = logging.getLogger(__name__)
console = Console()


_DEFAULT_REFUSAL_LIMIT = 20
_DEFAULT_BY_TYPE_LIMIT = 50


@command_meta(
    canonical_name="inspect.refusals",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="List recent constitutional refusals",
)
@core_command(dangerous=False, requires_context=False)
# ID: e15b2f7c-2784-4056-b3f8-5dc79aba9537
async def refusals_list_cmd(
    ctx: typer.Context,
    limit: int = typer.Option(
        _DEFAULT_REFUSAL_LIMIT,
        "--limit",
        "-n",
        help="Maximum records to show",
    ),
    refusal_type: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type (boundary, confidence, extraction, etc.)",
    ),
    component: str | None = typer.Option(
        None, "--component", "-c", help="Filter by component ID"
    ),
    details: bool = typer.Option(
        False, "--details", "-d", help="Show detailed information"
    ),
):
    """List recent constitutional refusals via the API."""
    _ = ctx
    _ = component  # /v1/refusals doesn't currently expose a component filter.
    client = CoreApiClient()
    payload = await client.refusals_list(
        refusal_type=refusal_type, session_id=None, limit=limit
    )
    _render_refusals(payload, details=details)


@command_meta(
    canonical_name="inspect.refusal-stats",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Show refusal statistics and trends",
)
@core_command(dangerous=False, requires_context=False)
# ID: 212e0adc-7f66-4e42-9d03-2841309ef823
async def refusals_stats_cmd(
    ctx: typer.Context,
    days: int = typer.Option(
        7, "--days", "-d", help="Number of days to analyze (default: 7)"
    ),
):
    """Show refusal statistics and trends via /v1/refusals/stats."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.refusals_stats(days=days)
    _render_stats(payload)


@command_meta(
    canonical_name="inspect.refusals-by-type",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Show refusals of a specific type",
)
@core_command(dangerous=False, requires_context=False)
# ID: c223a4db-5da5-4089-803c-7b24f0e9e72a
async def refusals_by_type_cmd(
    ctx: typer.Context,
    refusal_type: str = typer.Argument(
        ...,
        help="Refusal type (boundary, confidence, extraction, quality, assumption, capability)",
    ),
    limit: int = typer.Option(
        _DEFAULT_BY_TYPE_LIMIT,
        "--limit",
        "-n",
        help="Maximum records to show",
    ),
):
    """Show refusals of a specific type."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.refusals_list(
        refusal_type=refusal_type, session_id=None, limit=limit
    )
    _render_refusals(payload, details=False)


@command_meta(
    canonical_name="inspect.refusals-by-session",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Show all refusals for a specific decision trace session",
)
@core_command(dangerous=False, requires_context=False)
# ID: 6e93b8a7-64e6-4c76-bded-429f6f65f2ee
async def refusals_by_session_cmd(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Decision trace session ID"),
):
    """Show all refusals for a specific decision trace session."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.refusals_list(
        refusal_type=None,
        session_id=session_id,
        limit=_DEFAULT_BY_TYPE_LIMIT,
    )
    _render_refusals(payload, details=True)


def _render_refusals(payload: dict, *, details: bool) -> None:
    """Render the refusals list returned by /v1/refusals."""
    refusals = payload.get("refusals", [])
    if not refusals:
        console.print("[yellow]No refusals found.[/yellow]")
        return

    console.print(
        f"[cyan]Found {payload.get('count', len(refusals))} refusal(s)[/cyan]\n"
    )
    table = Table(title="Constitutional Refusals")
    table.add_column("ID", style="dim")
    table.add_column("Component", style="cyan")
    table.add_column("Phase", style="magenta")
    table.add_column("Type", style="yellow")
    table.add_column("Created", style="dim")
    for refusal in refusals:
        table.add_row(
            str(refusal.get("id") or "")[:8],
            str(refusal.get("component_id") or ""),
            str(refusal.get("phase") or ""),
            str(refusal.get("refusal_type") or ""),
            str(refusal.get("created_at") or "")[:19],
        )
    console.print(table)

    if details:
        for refusal in refusals:
            console.print(
                f"\n[bold cyan]{refusal.get('component_id')} — "
                f"{refusal.get('refusal_type')}[/bold cyan]"
            )
            reason = refusal.get("reason")
            if reason:
                console.print(f"Reason: {reason}")
            suggested = refusal.get("suggested_action")
            if suggested:
                console.print(f"Suggested: {suggested}")


def _render_stats(payload: dict) -> None:
    """Render /v1/refusals/stats payload."""
    counts = payload.get("counts_by_type") or {}
    stats = payload.get("stats") or {}
    console.print(f"[cyan]Lookback: {payload.get('days', 7)} day(s)[/cyan]\n")

    if counts:
        table = Table(title="Refusals by Type")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right")
        for refusal_type, count in sorted(
            counts.items(), key=lambda x: x[1], reverse=True
        ):
            table.add_row(str(refusal_type), str(count))
        console.print(table)

    if stats:
        console.print("\n[bold]Aggregate stats:[/bold]")
        for key, value in stats.items():
            console.print(f"  {key}: {value}")


refusals_commands = [
    {"name": "refusals", "func": refusals_list_cmd},
    {"name": "refusal-stats", "func": refusals_stats_cmd},
    {"name": "refusals-by-type", "func": refusals_by_type_cmd},
    {"name": "refusals-by-session", "func": refusals_by_session_cmd},
]
