# src/features/maintenance/dotenv_sync_service.py
"""
Provides a service to synchronize runtime configuration from the .env file
into the database, governed by the runtime_requirements.yaml policy.
"""

from __future__ import annotations

from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table
from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from sqlalchemy import Boolean, Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import declarative_base

log = getLogger("dotenv_sync_service")
console = Console()

# Define an ORM model matching the new table for type safety and ease of use.
Base = declarative_base()


# ID: 1b903819-4d34-4bf8-98f9-34c322d29676
class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"
    __table_args__ = {"schema": "core"}
    key = Column(Text, primary_key=True)
    value = Column(Text)
    description = Column(Text)
    is_secret = Column(Boolean, nullable=False, default=False)
    last_updated = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ID: 46c39446-1163-4d8d-ad63-5956a248260f
async def run_dotenv_sync(dry_run: bool):
    """
    Reads variables defined in runtime_requirements.yaml from the environment/.env
    and upserts them into the core.runtime_settings table.
    """
    console.print(
        "[bold cyan]🚀 Synchronizing .env configuration to database...[/bold cyan]"
    )

    try:
        runtime_reqs = settings.load("mind.config.runtime_requirements")
        variables_to_sync = runtime_reqs.get("variables", {})
    except FileNotFoundError as e:
        console.print(
            f"[bold red]❌ Error: Cannot find runtime_requirements policy: {e}[/bold red]"
        )
        return

    settings_to_upsert: List[Dict[str, Any]] = []
    for key, config in variables_to_sync.items():
        value = getattr(settings, key, None)

        # Ensure value is a string for the database, handling bools etc.
        if value is None:
            value_str = None
        elif isinstance(value, bool):
            value_str = str(value).lower()
        else:
            value_str = str(value)

        is_secret = config.get("source") == "secret" or "_KEY" in key or "_TOKEN" in key
        settings_to_upsert.append(
            {
                "key": key,
                "value": value_str,
                "description": config.get("description"),
                "is_secret": is_secret,
            }
        )

    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: The following settings would be synced --[/bold yellow]"
        )
        table = Table(title="Configuration Sync Plan")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="magenta")
        table.add_column("Is Secret?", style="red")

        for setting in settings_to_upsert:
            display_value = (
                "********"
                if setting["is_secret"] and setting["value"]
                else str(setting["value"])
            )
            table.add_row(setting["key"], display_value, str(setting["is_secret"]))
        console.print(table)
        return

    try:
        async with get_session() as session:
            async with session.begin():
                stmt = pg_insert(RuntimeSetting).values(settings_to_upsert)
                update_dict = {
                    "value": stmt.excluded.value,
                    "description": stmt.excluded.description,
                    "is_secret": stmt.excluded.is_secret,
                    "last_updated": func.now(),
                }
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["key"],
                    set_=update_dict,
                )
                await session.execute(upsert_stmt)

        console.print(
            f"[bold green]✅ Successfully synchronized {len(settings_to_upsert)} settings to the database.[/bold green]"
        )
    except Exception as e:
        log.error(f"Database sync failed: {e}", exc_info=True)
        console.print(
            f"[bold red]❌ Error: Failed to write to the database: {e}[/bold red]"
        )
