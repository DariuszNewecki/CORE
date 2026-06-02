# src/cli/logic/db.py

"""
Registers the top-level 'db' command group for managing the CORE operational database.

- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Redirected Mind-layer exports to the 'var/' runtime directory to maintain
  the read-only boundary of '.intent/'.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from sqlalchemy import text

from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.path_resolver import PathResolver

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


async def _export_vector_metadata(file_handler: FileHandler, repo_root: Path):
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

    content_str = yaml.dump(vector_data, indent=2, sort_keys=False)
    rel_path = str(
        (
            PathResolver.from_repo(repo_root).reports_dir
            / "vector_metadata_export.yaml"
        ).relative_to(repo_root)
    )

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
    await _export_vector_metadata(file_handler, core_context.git_service.repo_path)
    logger.info("Export complete.")


db_app.command("sync-domains")(sync_domains)


@db_app.command("migrate")
# ID: e8d94b4b-0257-4b03-8c83-03f04d8fb2a8
async def migrate_db_command(
    apply: bool = typer.Option(
        False, "--apply", help="(Currently inert — framework is dormant.)"
    ),
) -> None:
    """Show the current migration-framework status (currently dormant).

    The repo operates under a schema-as-truth model — `infra/sql/db_schema_live.sql`
    is the canonical schema. One-off SQL files under `infra/scripts/migrations/`
    are historical record and are NOT replayed through this CLI. See #438.
    """
    _ = apply  # currently unused; kept for forward-compat
    from rich.console import Console

    _console = Console()
    _console.print()
    _console.print("[yellow]⏸  Migration framework is currently dormant.[/yellow]")
    _console.print()
    _console.print("Schema-as-truth model is in effect:")
    _console.print("  • Canonical schema:  [cyan]infra/sql/db_schema_live.sql[/cyan]")
    _console.print(
        "  • Regenerate via:    [cyan]pg_dump --schema-only --schema=core[/cyan]"
    )
    _console.print(
        "  • One-off SQL files: [cyan]infra/scripts/migrations/[/cyan] (historical record)"
    )
    _console.print()
    _console.print(
        "This command will be revived if ledger-based migrations are reintroduced."
    )
    _console.print("See #438 for the framework-orphan history.")


db_app.command("migrate")(migrate_db_command)
