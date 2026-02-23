# src/body/cli/logic/db.py

"""
Registers the top-level 'db' command group for managing the CORE operational database.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Redirected Mind-layer exports to the 'var/' runtime directory to maintain
  the read-only boundary of '.intent/'.
"""

from __future__ import annotations

import typer
import yaml
from sqlalchemy import text

from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    migrate_db,
)
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger

from .sync_domains import sync_domains


logger = getLogger(__name__)
db_app = typer.Typer(
    help="Commands for managing the CORE operational database (migrations, syncs, status, exports)."
)


async def _export_domains(file_handler: FileHandler):
    """Fetches domains from the DB and writes them to the runtime knowledge directory."""
    logger.info("Exporting `core.domains` to YAML...")
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT key as name, title, description FROM core.domains ORDER BY key"
            )
        )
        domains_data = [dict(row._mapping) for row in result]

    # CONSTITUTIONAL FIX: Use var/ (runtime) instead of .intent/ (mind) for exports.
    # The Body layer must never write directly to the Constitution.
    yaml_content = {"version": 2, "domains": domains_data}
    content_str = yaml.dump(yaml_content, indent=2, sort_keys=False)

    # Resolve the relative path under the project root
    # Note: var/mind/knowledge/ is the canonical home for runtime knowledge artifacts.
    rel_path = "var/mind/knowledge/domains.yaml"

    # Governed write: checks IntentGuard and logs the action
    file_handler.write_runtime_text(rel_path, content_str)

    logger.info(
        "Wrote %s domains to %s",
        len(domains_data),
        rel_path,
    )


async def _export_vector_metadata(file_handler: FileHandler):
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

    # CONSTITUTIONAL FIX: Use FileHandler for report generation
    content_str = yaml.dump(vector_data, indent=2, sort_keys=False)
    rel_path = "reports/vector_metadata_export.yaml"

    file_handler.write_runtime_text(rel_path, content_str)

    logger.info(
        "Wrote metadata for %s vectors to %s",
        len(vector_data),
        rel_path,
    )


@db_app.command(
    "export", help="Export operational data from the database to read-only files."
)
# ID: 86554413-b670-4c62-80eb-31bab9a05edf
async def export_data(ctx: typer.Context) -> None:
    """Exports DB tables to their canonical, read-only YAML file representations."""
    core_context: CoreContext = ctx.obj
    logger.info("Exporting operational data from Database to files...")

    # Create the governed mutation surface
    file_handler = FileHandler(str(core_context.git_service.repo_path))

    await _export_domains(file_handler)
    await _export_vector_metadata(file_handler)
    logger.info("Export complete.")


db_app.command("sync-domains")(sync_domains)


@db_app.command("migrate")
# ID: e8d94b4b-0257-4b03-8c83-03f04d8fb2a8
async def migrate_db_command(
    apply: bool = typer.Option(
        False, "--apply", help="Apply pending migrations (default: dry run)."
    ),
) -> None:
    """Initialize DB schema and apply pending migrations."""
    try:
        await migrate_db(apply)
    except MigrationServiceError as exc:
        logger.error("%s", exc)
        raise typer.Exit(exc.exit_code) from exc


db_app.command("migrate")(migrate_db_command)
