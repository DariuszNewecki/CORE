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
from rich.console import Console
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.database.models import CliCommand
from services.database.session_manager import get_session
from shared.config import settings

console = Console()
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
# ID: 89be20b9-1d77-408f-9f59-3ac2ca169144
def hub_list_cmd() -> None:
    """Show all registered CLI commands from the DB registry."""

    async def _run() -> None:
        async with get_session() as session:
            cmds = await _fetch_commands(session)
        if not cmds:
            console.print(
                "[bold yellow]No CLI registry entries in DB.[/bold yellow] "
                "Run: [bold]core-admin knowledge sync[/bold]"
            )
            raise typer.Exit(code=2)
        table = Table(title="All CLI commands in registry")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Command", style="cyan")
        table.add_column("Module", style="magenta")
        table.add_column("Entrypoint", style="green")
        table.add_column("Description")
        for i, c in enumerate(cmds, 1):
            table.add_row(
                str(i),
                _format_command_name(c),
                getattr(c, "module", "") or "",
                getattr(c, "entrypoint", "") or "",
                _shorten(_desc_for(c), 100),
            )
        console.print(table)

    asyncio.run(_run())


@hub_app.command("search")
# ID: 8ac36c7c-867c-4f17-9503-5b5199cb813e
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
            console.print(
                "[bold yellow]No CLI registry entries found in DB.[/bold yellow]\n"
                "Try:\n"
                "  • core-admin knowledge migrate-ssot    (if you still have legacy YAML)\n"
                "  • core-admin knowledge sync            (introspect and populate)\n"
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
            console.print("[yellow]No matches.[/yellow]")
            raise typer.Exit(code=0)
        table = Table(title=f"Hub search: “{term}”")
        table.add_column("Command", style="cyan")
        table.add_column("Module", style="magenta")
        table.add_column("Entrypoint", style="green")
        table.add_column("Description", style="white")
        for c in hits:
            table.add_row(
                _format_command_name(c),
                getattr(c, "module", "") or "",
                getattr(c, "entrypoint", "") or "",
                _shorten(_desc_for(c), 100),
            )
        console.print(table)

    asyncio.run(_run())


@hub_app.command("whereis")
# ID: 263425b5-3e99-4e3b-a89f-0fc4b88d3fdd
def hub_whereis_cmd(
    command: str = typer.Argument(
        ...,
        help=(
            "Exact command name as stored (e.g., 'proposals.micro.apply' or "
            "'knowledge.sync')"
        ),
    ),
) -> None:
    """Show module, entrypoint, and file path for a command."""

    async def _run() -> None:
        async with get_session() as session:
            cmds = await _fetch_commands(session)
        if not cmds:
            console.print(
                "[bold yellow]No CLI registry in DB.[/bold yellow] "
                "Run [bold]core-admin knowledge sync[/bold] first."
            )
            raise typer.Exit(code=2)
        matches = [c for c in cmds if _format_command_name(c) == command]
        if not matches:
            matches = [c for c in cmds if _format_command_name(c).endswith(command)]
        if not matches:
            console.print("[yellow]No such command in registry.[/yellow]")
            raise typer.Exit(code=1)
        c = matches[0]
        path = (
            _module_file(getattr(c, "module", "") or "")
            if getattr(c, "module", None)
            else None
        )
        console.print(f"[bold]Command:[/bold] {_format_command_name(c)}")
        console.print(f"[bold]Module:[/bold]  {getattr(c, 'module', '') or '—'}")
        console.print(f"[bold]Entrypoint:[/bold] {getattr(c, 'entrypoint', '') or '—'}")
        console.print(f"[bold]File:[/bold]    {(path if path else '—')}")

    asyncio.run(_run())


@hub_app.command("doctor")
# ID: a09b6ebe-6a2a-4030-b85c-e9f127e74171
def hub_doctor_cmd() -> None:
    """Quick health checks for discoverability + SSOT surfaces."""

    async def _run() -> None:
        ok = True
        async with get_session() as session:
            try:
                cmds = await _fetch_commands(session)
                if cmds:
                    console.print(f"✅ CLI registry entries in DB: {len(cmds)}")
                else:
                    ok = False
                    console.print("❌ No CLI registry entries in DB.")
                    console.print("   → Run: core-admin knowledge sync")
            except Exception as e:
                ok = False
                console.print(f"❌ DB error while reading CLI registry: {e}")
        snapshots = [
            settings.MIND / "knowledge" / "cli_registry.yaml",
            settings.MIND / "knowledge" / "resource_manifest.yaml",
            settings.MIND / "knowledge" / "cognitive_roles.yaml",
        ]
        missing = [p for p in snapshots if not p.exists()]
        if missing:
            console.print("⚠️  Missing YAML exports:")
            for p in missing:
                console.print(f"   • {p}")
            console.print("   → Run: core-admin knowledge export-ssot")
        else:
            console.print("✅ YAML exports present.")
        console.print(
            "\nTip: run [bold]core-admin knowledge canary --skip-tests[/bold] before big ops."
        )
        raise typer.Exit(code=0 if ok else 1)

    asyncio.run(_run())
