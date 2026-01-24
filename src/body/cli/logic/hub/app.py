# src/body/cli/logic/hub/app.py

"""Refactored logic for src/body/cli/logic/hub/app.py."""

from __future__ import annotations

import typer

from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

from . import formatter
from .introspection import resolve_module_file
from .repository import fetch_all_commands


logger = getLogger(__name__)
hub_app = typer.Typer(help="Central hub for discovering and locating CORE tools.")


@hub_app.command("list")
# ID: 14cddd2d-c6d2-4ef9-8a22-378f669105fe
async def hub_list_cmd() -> list[dict[str, str | int]]:
    async with get_session() as session:
        cmds = await fetch_all_commands(session)
    if not cmds:
        logger.warning("No CLI registry entries in DB.")
        raise typer.Exit(code=2)

    result = []
    for i, c in enumerate(cmds, 1):
        result.append(
            {
                "index": i,
                "command": formatter.format_name(c),
                "module": getattr(c, "module", "") or "",
                "entrypoint": getattr(c, "entrypoint", "") or "",
                "description": formatter.shorten(formatter.get_description(c), 100),
            }
        )
    return result


@hub_app.command("search")
# ID: 4768a34f-4d69-4da5-bb32-80e4f018826a
async def hub_search_cmd(
    term: str = typer.Argument(..., help="Term to search."),
    limit: int = typer.Option(25, "--limit", "-l"),
) -> list[dict[str, str]]:
    async with get_session() as session:
        cmds = await fetch_all_commands(session)
    if not cmds:
        raise typer.Exit(code=2)

    term_l = term.lower()
    hits = [
        c
        for c in cmds
        if term_l in formatter.format_name(c).lower()
        or term_l in formatter.get_description(c).lower()
    ]

    if not hits:
        raise typer.Exit(code=0)
    return [
        {
            "command": formatter.format_name(c),
            "module": getattr(c, "module", "") or "",
            "description": formatter.shorten(formatter.get_description(c), 100),
        }
        for c in hits[:limit]
    ]


@hub_app.command("whereis")
# ID: 13c11806-3875-45d7-b5cb-ac8dd29df5cc
async def hub_whereis_cmd(command: str = typer.Argument(...)):
    async with get_session() as session:
        cmds = await fetch_all_commands(session)
    matches = [c for c in cmds if formatter.format_name(c) == command]
    if not matches:
        raise typer.Exit(code=1)
    c = matches[0]
    path = resolve_module_file(getattr(c, "module", "") or "")
    return {
        "command": formatter.format_name(c),
        "file": str(path) if path else "—",
    }


@hub_app.command("doctor")
# ID: dbac2d74-929e-47ca-a74a-32d192b274b9
async def hub_doctor_cmd(ctx: typer.Context) -> dict[str, object]:
    async with get_session() as session:
        cmds = await fetch_all_commands(session)
        count = len(cmds)

    core_context: CoreContext = ctx.obj
    exports_dir = core_context.git_service.repo_path / "var" / "mind" / "knowledge"
    yaml_count = len(list(exports_dir.glob("*.yaml"))) if exports_dir.exists() else 0

    return {
        "ok": count > 0,
        "cli_registry_count": count,
        "yaml_export_count": yaml_count,
    }
