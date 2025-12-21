# src/body/cli/logic/sync_domains.py
"""
CLI command to synchronize the canonical list of domains to the database.
"""

from __future__ import annotations

import typer
import yaml
from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


async def _sync_domains():
    """
    Reads the canonical domains.yaml file and upserts them into the core.domains table.
    """
    domains_path = settings.MIND / "knowledge" / "domains.yaml"
    if not domains_path.exists():
        logger.error("Constitutional domains file not found at %s", domains_path)
        raise typer.Exit(code=1)

    content = yaml.safe_load(domains_path.read_text("utf-8"))
    domains_to_sync = content.get("domains", [])

    if not domains_to_sync:
        logger.warning("No domains found in domains.yaml. Nothing to sync.")
        return

    upserted_count = 0
    async with get_session() as session:
        async with session.begin():  # Start a transaction
            for domain_data in domains_to_sync:
                name = domain_data.get("name")
                description = domain_data.get("description", "")
                if not name:
                    continue

                stmt = text(
                    """
                    INSERT INTO core.domains (key, title, description, status)
                    VALUES (:key, :title, :desc, 'active')
                    ON CONFLICT (key) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description;
                """
                )

                await session.execute(
                    stmt,
                    {
                        "key": name,
                        "title": name.replace("_", " ").title(),
                        "desc": description,
                    },
                )
                upserted_count += 1

    logger.info("Successfully synced %s domains to the database.", upserted_count)


# ID: 5bee5341-7f72-430e-b310-f174af37de20
async def sync_domains():
    """Synchronizes the canonical list of domains from .intent/knowledge/domains.yaml to the database."""
    await _sync_domains()
