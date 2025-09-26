# src/cli/commands/knowledge_sync.py
"""
CLI command for synchronizing operational knowledge from YAML files to the database.
"""
from __future__ import annotations

import asyncio
import json

import typer
import yaml
from rich.console import Console
from sqlalchemy import JSON, Column, MetaData, String, Table, dialects

from services.repositories.db.engine import get_session
from shared.config import settings

console = Console()


# --- THIS IS THE FIX ---
async def _upsert_data(session, table_name: str, data: list[dict], primary_key: str):
    """Generic upsert function for operational tables."""
    if not data:
        return 0

    meta = MetaData()
    # Reflect the table structure from the database to get columns, or define manually
    # For robustness, we'll define it based on what we know from the YAML and schema.
    columns = [Column(pk, String, primary_key=True) for pk in primary_key.split(",")]
    for key, value in data[0].items():
        if key not in primary_key:
            col_type = JSON if isinstance(value, (dict, list)) else String
            columns.append(Column(key, col_type))

    # Re-serialize JSON fields to strings for the DB driver
    for row in data:
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value)

    table_obj = Table(
        table_name.split(".")[-1], meta, *columns, schema=table_name.split(".")[0]
    )

    stmt = dialects.postgresql.insert(table_obj).values(data)
    update_dict = {c.name: c for c in stmt.excluded if not c.primary_key}

    upsert_stmt = stmt.on_conflict_do_update(
        index_elements=[primary_key],
        set_=update_dict,
    )

    result = await session.execute(upsert_stmt)
    return result.rowcount


# --- END OF FIX ---


async def _sync_operational_knowledge():
    """Reads legacy YAMLs and syncs them to the new DB tables."""
    console.print(
        "[bold cyan]🚀 Syncing operational knowledge from legacy YAMLs to Database...[/bold cyan]"
    )

    repo_root = settings.REPO_PATH

    # Define legacy paths and target tables
    sync_map = {
        "llm_resources": (
            repo_root / ".intent/charter/policies/agent/resource_manifest_policy.yaml",
            "llm_resources",
            "name",
        ),
        "cognitive_roles": (
            repo_root / ".intent/charter/policies/agent/cognitive_roles_policy.yaml",
            "cognitive_roles",
            "role",
        ),
        "runtime_services": (
            repo_root / ".intent/mind/config/runtime_services.yaml",
            "services",
            "name",
        ),
        "cli_commands": (
            repo_root / ".intent/charter/policies/governance/cli_registry_policy.yaml",
            "commands",
            "name",
        ),
    }

    total_upserted = 0
    async with get_session() as session:
        async with session.begin():
            for table, (path, key, pk) in sync_map.items():
                if not path.exists():
                    console.print(
                        f"[yellow]Legacy file not found, skipping: {path.relative_to(repo_root)}[/yellow]"
                    )
                    continue

                content = yaml.safe_load(path.read_text("utf-8"))
                records = content.get(key, [])

                if records:
                    console.print(
                        f"   -> Syncing {len(records)} records to core.{table}..."
                    )
                    upserted_count = await _upsert_data(
                        session, f"core.{table}", records, pk
                    )
                    total_upserted += upserted_count
                else:
                    console.print(
                        f"   -> No records found in {path.name} for key '{key}'."
                    )

    console.print(
        f"[bold green]✅ Sync complete. Acknowledged {total_upserted} records for upsert.[/bold green]"
    )


# ID: 416af662-de55-4da5-8e73-5e8255e842de
def sync_operational(
    write: bool = typer.Option(
        False, "--write", help="Apply the changes to the database."
    )
):
    """
    One-way sync of operational knowledge (CLI, Roles, Resources) from YAML to DB.
    """
    if not write:
        console.print(
            "[bold yellow]-- DRY RUN --[/bold yellow]\n"
            "This command will read operational YAML files and sync their contents to the database.\n"
            "This is a one-way destructive operation for migration.\n"
            "Run with '--write' to apply changes to the database."
        )
        return

    asyncio.run(_sync_operational_knowledge())


# ID: 41e17c9c-abfb-4af2-9421-412f8c688bfc
def register(app: typer.Typer):
    """Register the 'knowledge sync-operational' command."""
    knowledge_app_group = next(
        (g for g in app.registered_groups if g.name == "knowledge"), None
    )

    if knowledge_app_group:
        knowledge_app = knowledge_app_group.typer_instance
        knowledge_app.command("sync-operational")(sync_operational)
    else:
        # Fallback for dynamic loading
        sync_op_app = typer.Typer(help="Sync operational knowledge to the DB.")
        sync_op_app.command("sync-operational")(sync_operational)
        app.add_typer(sync_op_app, name="knowledge")
