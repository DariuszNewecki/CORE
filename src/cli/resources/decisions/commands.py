# src/cli/resources/decisions/commands.py

"""``core-admin decisions show`` / ``decisions list`` — ADR answers (ADR-168 D4.3).

Read-only and service-free. Output is the same JSON the MCP tools
``decision_adr`` and ``decision_adrs`` return.
"""

from __future__ import annotations

import typer

from cli.utils import core_command
from cli.utils.assistant_output import run_tool
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)

from .hub import app


@app.command("show")
@command_meta(
    canonical_name="decisions.show",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.USER_FACING,
    summary="One ADR: id, title, status and decision headings, with its file.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: bdcf5084-7102-48c0-8968-0f2d2521d2b8
async def decisions_show(
    ctx: typer.Context,
    adr_id: str = typer.Argument(..., help="ADR id: ADR-168 or 168."),
) -> None:
    """
    Show one architecture decision record: id, title, status and its decision
    headings, with the file it lives in.

    Example: core-admin decisions show ADR-168
    """
    await run_tool("decision_adr", {"adr_id": adr_id})


@app.command("list")
@command_meta(
    canonical_name="decisions.list",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.USER_FACING,
    summary="Every ADR's id, title and status, optionally filtered by status.",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: 6a202fed-b750-4023-9172-7a18c57b412c
async def decisions_list(
    ctx: typer.Context,
    status: str | None = typer.Option(
        None, "--status", help="Only ADRs whose status begins with this, e.g. accepted."
    ),
) -> None:
    """
    List every ADR's id, title and status.

    Example: core-admin decisions list --status accepted
    """
    await run_tool("decision_adrs", {"status": status} if status else {})
