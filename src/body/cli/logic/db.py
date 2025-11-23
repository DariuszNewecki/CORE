# src/body/cli/logic/db.py
"""
Registers the top-level 'db' command group for managing the CORE operational database.
"""

from __future__ import annotations

import asyncio

import typer
import yaml
from rich.console import Console
from sqlalchemy import text

from services.database.session_manager import get_session
from services.repositories.db.migration_service import migrate_db
from shared.config import settings

from .sync_domains import sync_domains

console = Console()
db_app = typer.Typer(
    help="Commands for managing the CORE operational database (migrations, syncs, status, exports)."
)


async def _export_domains():
    """Fetches domains from the DB and writes them to domains.yaml."""
    console.print("   -> Exporting `core.domains` to YAML...")
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT key as name, title, description FROM core.domains ORDER BY key"
            )
        )
        domains_data = [dict(row._mapping) for row in result]

    output_path = settings.MIND / "knowledge" / "domains.yaml"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_content = {"version": 2, "domains": domains_data}
    output_path.write_text(yaml.dump(yaml_content, indent=2, sort_keys=False), "utf-8")
    console.print(
        f"      -> Wrote {len(domains_data)} domains to {output_path.relative_to(settings.REPO_PATH)}"
    )


async def _export_vector_metadata():
    """Fetches vector metadata from the DB and writes it to a report."""
    console.print("   -> Exporting vector metadata from database to YAML...")
    async with get_session() as session:
        # --- START OF FIX: Corrected the SQL query to use a JOIN ---
        result = await session.execute(
            text(
                """
                SELECT s.id as uuid, s.symbol_path, l.vector_id
                FROM core.symbols s
                JOIN core.symbol_vector_links l ON s.id = l.symbol_id
                ORDER BY s.symbol_path;
                """
            )
        )
        # --- END OF FIX ---

        # Convert UUIDs to strings for YAML serialization
        vector_data = []
        for row in result:
            row_dict = dict(row._mapping)
            if "uuid" in row_dict and row_dict["uuid"] is not None:
                row_dict["uuid"] = str(row_dict["uuid"])
            if "vector_id" in row_dict and row_dict["vector_id"] is not None:
                row_dict["vector_id"] = str(row_dict["vector_id"])
            vector_data.append(row_dict)

    output_path = settings.REPO_PATH / "reports" / "vector_metadata_export.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.dump(vector_data, indent=2, sort_keys=False), "utf-8")
    console.print(
        f"      -> Wrote metadata for {len(vector_data)} vectors to {output_path.relative_to(settings.REPO_PATH)}"
    )


@db_app.command(
    "export", help="Export operational data from the database to read-only files."
)
# ID: abcb819a-2a07-4c8e-a56e-3368478ce245
def export_data():
    """Exports DB tables to their canonical, read-only YAML file representations."""
    console.print(
        "[bold cyan]🚀 Exporting operational data from Database to files...[/bold cyan]"
    )

    async def _run_exports():
        await _export_domains()
        await _export_vector_metadata()

    asyncio.run(_run_exports())
    console.print("[bold green]✅ Export complete.[/bold green]")


db_app.command("sync-domains")(sync_domains)
db_app.command("migrate")(migrate_db)
