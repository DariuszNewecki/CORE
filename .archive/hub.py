# src/body/cli/logic/hub.py
# ID: body.cli.logic.hub
"""
Central Hub: discover and locate CORE tools from a single place.
Refactored for High-Fidelity (V2.3).
"""

from __future__ import annotations
from pathlib import Path
import typer
from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger

# Import our new specialized neurons
from .hub.repository import fetch_all_commands
from .hub.introspection import resolve_module_file
from .hub import formatter

logger = getLogger(__name__)
hub_app = typer.Typer(help="Central hub for discovering and locating CORE tools.")

@hub_app.command("list")
async def hub_list_cmd() -> list[dict[str, str | int]]:
    """Show all registered CLI commands from the DB registry."""
    async with get_session() as session:
        cmds = await fetch_all_commands(session)

    if not cmds:
        logger.warning("No CLI registry entries in DB. Run: core-admin knowledge sync")
        raise typer.Exit(code=2)

    result = []
    for i, c in enumerate(cmds, 1):
        result.append({
            "index": i,
            "command": formatter.format_name(c),
            "module": getattr(c, "module", "") or "",
            "entrypoint": getattr(c, "entrypoint", "") or "",
            "description": formatter.shorten(formatter.get_description(c), 100),
        })

    logger.info("Found %s CLI commands in registry", len(result))
    return result

@hub_app.command("search")
async def hub_search_cmd(
    term: str = typer.Argument(..., help="Term to search in command names/descriptions."),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results."),
) -> list[dict[str, str]]:
    """Fuzzy search across CLI commands from the registry."""
    async with get_session() as session:
        cmds = await fetch_all_commands(session)

    if not cmds:
        logger.warning("No CLI registry found in DB. Run knowledge sync.")
        raise typer.Exit(code=2)

    term_l = term.lower()
    hits = [c for c in cmds if term_l in formatter.format_name(c).lower() 
            or term_l in formatter.get_description(c).lower()]

    hits = hits[:limit]
    if not hits:
        logger.info("No matches found for term: %s", term)
        raise typer.Exit(code=0)

    result = []
    for c in hits:
        result.append({
            "command": formatter.format_name(c),
            "module": getattr(c, "module", "") or "",
            "entrypoint": getattr(c, "entrypoint", "") or "",
            "description": formatter.shorten(formatter.get_description(c), 100),
        })
    return result

@hub_app.command("whereis")
async def hub_whereis_cmd(
    command: str = typer.Argument(..., help="Exact command name (e.g., 'knowledge.sync')"),
) -> dict[str, str]:
    """Show module, entrypoint, and file path for a command."""
    async with get_session() as session:
        cmds = await fetch_all_commands(session)

    if not cmds:
        logger.warning("No CLI registry in DB.")
        raise typer.Exit(code=2)

    matches = [c for c in cmds if formatter.format_name(c) == command]
    if not matches:
        matches = [c for c in cmds if formatter.format_name(c).endswith(command)]

    if not matches:
        logger.warning("No such command in registry: %s", command)
        raise typer.Exit(code=1)

    c = matches[0]
    path = resolve_module_file(getattr(c, "module", "") or "") if getattr(c, "module", None) else None

    return {
        "command": formatter.format_name(c),
        "module": getattr(c, "module", "") or "—",
        "entrypoint": getattr(c, "entrypoint", "") or "—",
        "file": str(path) if path else "—",
    }

@hub_app.command("doctor")
async def hub_doctor_cmd() -> dict[str, object]:
    """Quick health checks for discoverability + SSOT surfaces."""
    ok = True
    async with get_session() as session:
        try:
            cmds = await fetch_all_commands(session)
            if cmds: logger.info("CLI registry entries in DB: %s", len(cmds))
            else:
                ok = False
                logger.warning("No CLI registry entries in DB.")
        except Exception as e:
            ok = False
            logger.error("DB error: %s", e)
            cmds = []

    exports_dir = settings.MIND / "knowledge"
    exports = [p for p in exports_dir.glob("*.yaml") if p.is_file()] if exports_dir.exists() else []

    if not exports: logger.warning("No YAML exports found under: %s", exports_dir)
    else: logger.info("YAML exports present: %s files", len(exports))

    return {
        "ok": ok, "cli_registry_count": len(cmds),
        "exports_dir": str(exports_dir), "yaml_export_count": len(exports),
    }