# src/body/cli/commands/inspect/refusals.py
# ID: dfd9d154-4779-449e-8847-24fff221ee57

"""
Constitutional refusal inspection commands.

Commands:
- inspect refusals - List recent refusals
- inspect refusal-stats - Show statistics
- inspect refusals-by-type - Filter by type
- inspect refusals-by-session - Audit specific session
"""

from __future__ import annotations

import typer

from shared.cli_utils import core_command
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta


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
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum records to show"),
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
    """
    List recent constitutional refusals.

    Constitutional Principle: "Refusal as first-class outcome"

    Examples:
        core-admin inspect refusals
        core-admin inspect refusals --limit 50
        core-admin inspect refusals --type extraction
        core-admin inspect refusals --component code_generator --details
    """
    from cli.logic.refusal_inspect_logic import show_recent_refusals

    await show_recent_refusals(
        limit=limit,
        refusal_type=refusal_type,
        component=component,
        details=details,
    )


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
    """
    Show refusal statistics and trends.

    Examples:
        core-admin inspect refusal-stats
        core-admin inspect refusal-stats --days 30
    """
    from cli.logic.refusal_inspect_logic import show_refusal_statistics

    await show_refusal_statistics(days=days)


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
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum records to show"),
):
    """
    Show refusals of a specific type.

    Examples:
        core-admin inspect refusals-by-type extraction
        core-admin inspect refusals-by-type boundary --limit 50
        core-admin inspect refusals-by-type confidence
    """
    from cli.logic.refusal_inspect_logic import show_refusals_by_type

    await show_refusals_by_type(refusal_type, limit=limit)


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
    """
    Show all refusals for a specific decision trace session.

    Examples:
        core-admin inspect refusals-by-session abc123def456
    """
    from cli.logic.refusal_inspect_logic import show_refusals_by_session

    await show_refusals_by_session(session_id)


# Export commands for registration
refusals_commands = [
    {"name": "refusals", "func": refusals_list_cmd},
    {"name": "refusal-stats", "func": refusals_stats_cmd},
    {"name": "refusals-by-type", "func": refusals_by_type_cmd},
    {"name": "refusals-by-session", "func": refusals_by_session_cmd},
]
