# src/cli/resources/mcp/run.py

"""``core-admin mcp run`` — serve the assistant surface over stdio (ADR-168 D4.3).

An assistant (Claude Code, Cursor, …) starts this command itself, in the
repository it works on. Local first: no database, no API, no other service.
"""

from __future__ import annotations

import typer

from cli.logic.mcp_server import serve_stdio
from cli.utils import core_command
from cli.utils.exit_codes import EXIT_CONFIG_ERROR
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)
from shared.path_utils import get_repo_root

from .hub import app


@app.command("run")
@command_meta(
    canonical_name="mcp.run",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.MIND,
    exposure=CommandExposure.USER_FACING,
    summary="Serve law, decisions and the fast verdict to an AI assistant over MCP (stdio).",
)
@core_command(dangerous=False, requires_context=False, requires_brain_services=False)
# ID: c14c7920-0eac-4342-8fe7-d70e48aa6e36
async def mcp_run(ctx: typer.Context) -> None:
    """
    Serve the assistant surface over stdio for the repository around the
    working directory. Every tool only reads; none can act as the governor.
    The assistant starts this itself; see docs for the one-line config.

    Example: claude mcp add core -- core-admin mcp run
    """
    try:
        repo_root = get_repo_root()
    except FileNotFoundError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc
    await serve_stdio(repo_root)
