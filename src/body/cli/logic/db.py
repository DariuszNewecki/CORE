# src/body/cli/logic/db.py

"""
Registers the top-level 'db' command group for managing the CORE operational database.
"""

from __future__ import annotations

import typer
import yaml
from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.db.migration_service import migrate_db
from shared.logger import getLogger

from .sync_domains import sync_domains


logger = getLogger(__name__)
db_app = typer.Typer(
    help="Commands for managing the CORE operational database (migrations, syncs, status, exports)."
)


async def _export_domains():
    """Fetches domains from the DB and writes them to domains.yaml."""
    logger.info("Exporting `core.domains` to YAML...")
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
    logger.info(
        "Wrote %s domains to %s",
        len(domains_data),
        output_path.relative_to(settings.REPO_PATH),
    )


async def _export_vector_metadata():
    """Fetches vector metadata from the DB and writes it to a report."""
    logger.info("Exporting vector metadata from database to YAML...")
    async with get_session() as session:
        result = await session.execute(
            text(
                "\n                SELECT s.id as uuid, s.symbol_path, l.vector_id\n                FROM core.symbols s\n                JOIN core.symbol_vector_links l ON s.id = l.symbol_id\n                ORDER BY s.symbol_path;\n                "
            )
        )
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
    logger.info(
        "Wrote metadata for %s vectors to %s",
        len(vector_data),
        output_path.relative_to(settings.REPO_PATH),
    )


@db_app.command(
    "export", help="Export operational data from the database to read-only files."
)
# ID: 86554413-b670-4c62-80eb-31bab9a05edf
async def export_data() -> None:
    """Exports DB tables to their canonical, read-only YAML file representations."""
    logger.info("Exporting operational data from Database to files...")

    await _export_domains()
    await _export_vector_metadata()
    logger.info("Export complete.")


db_app.command("sync-domains")(sync_domains)
db_app.command("migrate")(migrate_db)
