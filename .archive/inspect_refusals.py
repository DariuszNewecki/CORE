# src/body/cli/commands/inspect_refusals.py
# ID: cli.commands.inspect_refusals

"""
CLI commands for inspecting constitutional refusals.

Commands:
- core-admin inspect refusals list [--limit N] [--type TYPE] [--component COMP]
- core-admin inspect refusals stats [--days N]
- core-admin inspect refusals by-type TYPE [--limit N]
- core-admin inspect refusals by-session SESSION_ID

Constitutional Compliance:
Enables auditing of "refusal as first-class outcome" principle.
"""

from __future__ import annotations

from typing import Optional

import typer

from body.cli.logic.refusal_inspect_logic import (
    show_recent_refusals,
    show_refusal_statistics,
    show_refusals_by_session,
    show_refusals_by_type,
)


app = typer.Typer(help="Inspect constitutional refusals")


# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
@app.command("list")
def list_refusals(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum records to show"),
    refusal_type: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type (boundary, confidence, extraction, etc.)",
    ),
    component: Optional[str] = typer.Option(
        None, "--component", "-c", help="Filter by component ID"
    ),
    details: bool = typer.Option(
        False, "--details", "-d", help="Show detailed information"
    ),
):
    """
    List recent constitutional refusals.

    Examples:
      core-admin inspect refusals list
      core-admin inspect refusals list --limit 50
      core-admin inspect refusals list --type extraction
      core-admin inspect refusals list --component code_generator --details
    """
    import asyncio

    asyncio.run(
        show_recent_refusals(
            limit=limit,
            refusal_type=refusal_type,
            component=component,
            details=details,
        )
    )


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
@app.command("stats")
def refusal_statistics(
    days: int = typer.Option(
        7, "--days", "-d", help="Number of days to analyze (default: 7)"
    ),
):
    """
    Show refusal statistics and trends.

    Examples:
      core-admin inspect refusals stats
      core-admin inspect refusals stats --days 30
    """
    import asyncio

    asyncio.run(show_refusal_statistics(days=days))


# ID: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
@app.command("by-type")
def refusals_by_type(
    refusal_type: str = typer.Argument(
        ...,
        help="Refusal type (boundary, confidence, extraction, quality, assumption, capability)",
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum records to show"),
):
    """
    Show refusals of a specific type.

    Examples:
      core-admin inspect refusals by-type extraction
      core-admin inspect refusals by-type boundary --limit 50
      core-admin inspect refusals by-type confidence
    """
    import asyncio

    asyncio.run(show_refusals_by_type(refusal_type, limit=limit))


# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
@app.command("by-session")
def refusals_by_session(
    session_id: str = typer.Argument(..., help="Decision trace session ID"),
):
    """
    Show all refusals for a specific decision trace session.

    Examples:
      core-admin inspect refusals by-session abc123def456
    """
    import asyncio

    asyncio.run(show_refusals_by_session(session_id))


# ID: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9a0b
@app.callback()
def refusals_callback():
    """
    Inspect constitutional refusals.

    Constitutional Principle: "Refusal as first-class outcome"

    Refusals are legitimate decisions, not errors. This command enables
    auditing constitutional refusal discipline across the system.
    """
    pass