# src/cli/logic/knowledge_sync.py
"""
CLI command for synchronizing operational knowledge from YAML files to the database.
"""
from __future__ import annotations

import asyncio

import yaml
from rich.console import Console
from sqlalchemy import JSON, Column, MetaData, String, Table
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.database.session_manager import get_session
from shared.config import settings
from shared.legacy_models import LegacyCognitiveRoles, LegacyResourceManifest

console = Console()


async def _upsert_data(session, table_name: str, data: list[dict], primary_key: str):
    """Generic upsert function for operational tables using PostgreSQL's ON CONFLICT."""
    if not data:
        return 0

    # Dynamically create a SQLAlchemy Table object for the upsert
    meta = MetaData()
    columns = [Column(pk, String, primary_key=True) for pk in primary_key.split(",")]
    for key, value in data[0].items():
        if key not in primary_key:
            col_type = JSON if isinstance(value, (dict, list)) else String
            columns.append(Column(key, col_type))

    table_obj = Table(
        table_name.split(".")[-1], meta, *columns, schema=table_name.split(".")[0]
    )

    # The database driver handles JSON serialization automatically.

    stmt = pg_insert(table_obj).values(data)
    update_dict = {
        c.name: getattr(stmt.excluded, c.name)
        for c in table_obj.columns
        if not c.primary_key
    }
    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=primary_key.split(","),
        set_=update_dict,
    )

    result = await session.execute(upsert_stmt)
    return result.rowcount


async def _sync_operational_knowledge():
    """Reads constitutional YAMLs and syncs them to the operational DB tables."""
    console.print(
        "[bold cyan]🚀 Syncing operational knowledge from constitution YAMLs to Database...[/bold cyan]"
    )

    sync_map = {
        "core.llm_resources": (
            settings.get_path("mind.knowledge.resource_manifest"),
            LegacyResourceManifest,
            "llm_resources",
            "name",
        ),
        "core.cognitive_roles": (
            settings.get_path("mind.knowledge.cognitive_roles"),
            LegacyCognitiveRoles,
            "cognitive_roles",
            "role",
        ),
    }

    total_upserted = 0
    async with get_session() as session:
        async with session.begin():
            for table_name, (path, model, key, pk) in sync_map.items():
                if not path.exists():
                    console.print(
                        f"[yellow]Constitutional file not found, skipping: {path.relative_to(settings.REPO_PATH)}[/yellow]"
                    )
                    continue

                try:
                    content = yaml.safe_load(path.read_text("utf-8"))
                    validated_data = model(**content)
                    records = [
                        item.model_dump() for item in getattr(validated_data, key)
                    ]

                    if records:
                        console.print(
                            f"   -> Syncing {len(records)} records to {table_name}..."
                        )
                        upserted_count = await _upsert_data(
                            session, table_name, records, pk
                        )
                        total_upserted += upserted_count
                except Exception as e:
                    console.print(
                        f"[bold red]❌ Failed to process or sync {path.name}: {e}[/bold red]"
                    )

    console.print(
        f"[bold green]✅ Sync complete. Acknowledged {total_upserted} records for upsert.[/bold green]"
    )


# ID: efcd71fb-4f20-4066-8eff-899781019575
def sync_operational():
    """One-way sync of operational knowledge (Roles, Resources) from YAML to DB."""
    asyncio.run(_sync_operational_knowledge())
