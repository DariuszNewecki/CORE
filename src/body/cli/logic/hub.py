# src/body/cli/logic/hub.py

"""
Central Hub: discover and locate CORE tools from a single place.

This reads from the DB-backed CLI registry (core.cli_commands). If empty, it
helps you populate it via `core-admin knowledge sync` or `migrate-ssot`.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
from pathlib import Path

import typer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.infrastructure.database.models import CliCommand
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
hub_app = typer.Typer(help="Central hub for discovering and locating CORE tools.")


async def _fetch_commands(session: AsyncSession) -> list[CliCommand]:
    rows = (await session.execute(select(CliCommand))).scalars().all()
    return list(rows or [])


def _format_command_name(cmd: CliCommand) -> str:
    return getattr(cmd, "name", "") or ""


def _shorten(s: str | None, n: int = 80) -> str:
    if not s:
        return "—"
    return s if len(s) <= n else s[: n - 1] + "…"


def _module_file(module_path: str) -> Path | None:
    try:
        mod = importlib.import_module(module_path)
        f = inspect.getsourcefile(mod)
        return Path(f).resolve() if f else None
    except Exception:
        return None


def _desc_for(c: CliCommand) -> str:
    """Best-effort description across possible schemas (be resilient to missing fields)."""
    for attr in ("description", "help", "summary", "doc"):
        v = getattr(c, attr, None)
        if isinstance(v, str) and v.strip():
            return v
    return ""


@hub_app.command("list")
# ID: 4ed85152-a34d-4621-b49e-c21c7d7ea65f
def hub_list_cmd() -> None:
    """Show all registered CLI commands from the DB registry."""

    async def _run() -> None:
        async with get_session() as session:
            cmds = await _fetch_commands(session)
        if not cmds:
            logger.warning(
                "No CLI registry entries in DB. Run: core-admin knowledge sync"
            )
            raise typer.Exit(code=2)
        result = []
        for i, c in enumerate(cmds, 1):
            result.append(
                {
                    "index": i,
                    "command": _format_command_name(c),
                    "module": getattr(c, "module", "") or "",
                    "entrypoint": getattr(c, "entrypoint", "") or "",
                    "description": _shorten(_desc_for(c), 100),
                }
            )
        logger.info("Found %s CLI commands in registry", len(result))
        return result

    result = asyncio.run(_run())


@hub_app.command("search")
# ID: 87f373a7-4fdc-4d20-b0f3-538d575d5901
def hub_search_cmd(
    term: str = typer.Argument(
        ..., help="Term to search in command names/descriptions."
    ),
    limit: int = typer.Option(25, "--limit", "-l", help="Max results."),
) -> None:
    """Fuzzy search across CLI commands from the registry."""

    async def _run() -> None:
        async with get_session() as session:
            cmds = await _fetch_commands(session)
        if not cmds:
            logger.warning(
                "No CLI registry entries found in DB. Try: core-admin knowledge migrate-ssot or core-admin knowledge sync"
            )
            raise typer.Exit(code=2)
        term_l = term.lower()
        hits: list[CliCommand] = []
        for c in cmds:
            name = (_format_command_name(c) or "").lower()
            desc = _desc_for(c).lower()
            if term_l in name or (desc and term_l in desc):
                hits.append(c)
        hits = hits[:limit]
        if not hits:
            logger.info("No matches found for term: %s", term)
            raise typer.Exit(code=0)
        result = []
        for c in hits:
            result.append(
                {
                    "command": _format_command_name(c),
                    "module": getattr(c, "module", "") or "",
                    "entrypoint": getattr(c, "entrypoint", "") or "",
                    "description": _shorten(_desc_for(c), 100),
                }
            )
        logger.info("Found {len(result)} matches for term: %s", term)
        return result

    result = asyncio.run(_run())


@hub_app.command("whereis")
# ID: 22947253-ef43-4869-8590-f4a1020a9853
def hub_whereis_cmd(
    command: str = typer.Argument(
        ...,
        help="Exact command name as stored (e.g., 'proposals.micro.apply' or 'knowledge.sync')",
    ),
) -> None:
    """Show module, entrypoint, and file path for a command."""

    async def _run() -> None:
        async with get_session() as session:
            cmds = await _fetch_commands(session)
        if not cmds:
            logger.warning(
                "No CLI registry in DB. Run core-admin knowledge sync first."
            )
            raise typer.Exit(code=2)
        matches = [c for c in cmds if _format_command_name(c) == command]
        if not matches:
            matches = [c for c in cmds if _format_command_name(c).endswith(command)]
        if not matches:
            logger.warning("No such command in registry: %s", command)
            raise typer.Exit(code=1)
        c = matches[0]
        path = (
            _module_file(getattr(c, "module", "") or "")
            if getattr(c, "module", None)
            else None
        )
        result = {
            "command": _format_command_name(c),
            "module": getattr(c, "module", "") or "—",
            "entrypoint": getattr(c, "entrypoint", "") or "—",
            "file": str(path) if path else "—",
        }
        logger.info("Found command details for: %s", command)
        return result

    result = asyncio.run(_run())


@hub_app.command("doctor")
# ID: c7168a36-d55f-4830-8f87-47530ba64ae7
def hub_doctor_cmd() -> None:
    """Quick health checks for discoverability + SSOT surfaces."""

    async def _run() -> None:
        ok = True
        async with get_session() as session:
            try:
                cmds = await _fetch_commands(session)
                if cmds:
                    logger.info("CLI registry entries in DB: %s", len(cmds))
                else:
                    ok = False
                    logger.warning(
                        "No CLI registry entries in DB. Run: core-admin knowledge sync"
                    )
            except Exception as e:
                ok = False
                logger.error("DB error while reading CLI registry: %s", e)
        snapshots = [
            settings.MIND / "knowledge" / "cli_registry.yaml",
            settings.MIND / "knowledge" / "resource_manifest.yaml",
            settings.MIND / "knowledge" / "cognitive_roles.yaml",
        ]
        missing = [p for p in snapshots if not p.exists()]
        if missing:
            logger.warning("Missing YAML exports:")
            for p in missing:
                logger.warning("  • %s", p)
            logger.warning("Run: core-admin knowledge export-ssot")
        else:
            logger.info("YAML exports present.")
        logger.info("Tip: run core-admin knowledge canary --skip-tests before big ops.")
        result = {
            "ok": ok,
            "cli_registry_count": len(cmds) if "cmds" in locals() else 0,
            "missing_yaml_exports": [str(p) for p in missing],
        }
        return result

    result = asyncio.run(_run())
