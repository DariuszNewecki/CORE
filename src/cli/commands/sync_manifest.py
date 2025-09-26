# src/cli/commands/sync_manifest.py
"""
Implements the 'knowledge sync-manifest' command to synchronize the project
manifest with the public symbols stored in the database.
"""
from __future__ import annotations

import asyncio

import typer
import yaml
from rich.console import Console
from sqlalchemy import text

from services.repositories.db.engine import get_session
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.sync_manifest")
console = Console()

MANIFEST_PATH = settings.REPO_PATH / ".intent" / "mind" / "project_manifest.yaml"


async def _async_sync_manifest():
    """
    Reads all public symbols from the database and updates project_manifest.yaml
    to make it the single source of truth for all declared capabilities.
    """
    console.print(
        "[bold cyan]🚀 Synchronizing project manifest with database...[/bold cyan]"
    )

    if not MANIFEST_PATH.exists():
        log.error(f"❌ Manifest file not found at {MANIFEST_PATH}")
        raise typer.Exit(code=1)

    console.print("   -> Fetching all public symbols from the database...")
    public_symbol_keys = []
    try:
        async with get_session() as session:
            result = await session.execute(
                text(
                    "SELECT key FROM core.symbols WHERE is_public = TRUE AND key IS NOT NULL ORDER BY key"
                )
            )
            public_symbol_keys = [row[0] for row in result]
    except Exception as e:
        log.error(f"❌ Database query failed: {e}")
        console.print(
            "[bold red]Error connecting to the database. Is it running?[/bold red]"
        )
        raise typer.Exit(code=1)

    console.print(
        f"   -> Found {len(public_symbol_keys)} public capabilities to declare."
    )

    console.print(f"   -> Updating {MANIFEST_PATH.relative_to(settings.REPO_PATH)}...")
    manifest_data = yaml.safe_load(MANIFEST_PATH.read_text("utf-8"))
    manifest_data["capabilities"] = public_symbol_keys

    MANIFEST_PATH.write_text(
        yaml.dump(manifest_data, indent=2, sort_keys=False), "utf-8"
    )

    console.print("[bold green]✅ Manifest synchronization complete.[/bold green]")


# ID: fcf8c754-27d0-4449-a3c4-bd3afbcff6ce
def sync_manifest():
    """Synchronizes project_manifest.yaml with the public capabilities in the database."""
    asyncio.run(_async_sync_manifest())
