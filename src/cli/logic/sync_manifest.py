# src/cli/logic/sync_manifest.py
"""
Implements the 'knowledge sync-manifest' command to synchronize the project
manifest with the public symbols stored in the database.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from ruamel.yaml import YAML  # Use ruamel.yaml for safer writing
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import text

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
                    # Fetch keys from symbols that have a non-null key
                    "SELECT key FROM core.symbols WHERE key IS NOT NULL ORDER BY key"
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

    yaml_handler = YAML()
    yaml_handler.indent(mapping=2, sequence=4, offset=2)

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest_data = yaml_handler.load(f)

    manifest_data["capabilities"] = public_symbol_keys

    console.print(f"   -> Updating {MANIFEST_PATH.relative_to(settings.REPO_PATH)}...")

    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        yaml_handler.dump(manifest_data, f)

    console.print("[bold green]✅ Manifest synchronization complete.[/bold green]")


# ID: fcf8c754-27d0-4449-a3c4-bd3afbcff6ce
def sync_manifest():
    """Synchronizes project_manifest.yaml with the public capabilities in the database."""
    asyncio.run(_async_sync_manifest())
