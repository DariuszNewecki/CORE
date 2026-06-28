# src/cli/commands/inspect/status.py
"""System and database status inspection commands."""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command
from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    command_meta,
)


logger = logging.getLogger(__name__)
console = Console()


@command_meta(
    canonical_name="inspect.status",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    exposure=CommandExposure.USER_FACING,
    summary="Display database connection and migration status",
)
@core_command(dangerous=False, requires_context=False)
# ID: 4d56d191-4d50-41f6-8d64-cc5732a92186
async def status_command(ctx: typer.Context) -> None:
    """Display database connection and schema state via /v1/status/db."""
    _ = ctx
    client = CoreApiClient()
    payload = await client.status_db()
    if payload.get("connected"):
        console.print("Database connection: OK")
    else:
        console.print("Database connection: FAILED")
        error = payload.get("error")
        if error:
            console.print(f"  {error}")
    tables = payload.get("core_schema_tables")
    if tables is not None:
        console.print(f"core schema tables: {tables}")
    warning = payload.get("warning")
    if warning:
        console.print(f"[yellow]{warning}[/yellow]")


status_commands = [{"name": "status", "func": status_command}]
