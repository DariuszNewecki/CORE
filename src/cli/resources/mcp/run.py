# src/cli/resources/mcp/run.py

"""``core-admin mcp run`` — serve the assistant surface over stdio (ADR-168 D4.3).

An assistant (Claude Code, Cursor, …) starts this command itself, in the
repository it works on. Local first: no database, no API, no other service.
"""

from __future__ import annotations

from pathlib import Path

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
async def mcp_run(
    ctx: typer.Context,
    repo: Path | None = typer.Option(
        None,
        "--repo",
        help=(
            "The project to serve (it, or a parent, must hold .intent/). "
            "Default: the working directory. Assistants that do not promise a "
            "working directory pass the project root here."
        ),
    ),
) -> None:
    """
    Serve the assistant surface over stdio for one project. Every tool only
    reads; none can act as the governor. The assistant starts this itself;
    see docs/connect-an-assistant.md for the configuration.

    Example: claude mcp add --scope project core -- core-admin mcp run
    """
    try:
        repo_root = get_repo_root(start_dir=repo.resolve() if repo else None)
    except FileNotFoundError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc
    await serve_stdio(repo_root)
