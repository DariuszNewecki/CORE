# src/body/cli/logic/knowledge_sync/snapshot.py
"""
Handles snapshot operations to export database state to YAML files for the CORE Working Mind.
"""

from __future__ import annotations

import asyncio
import getpass
from typing import Any

from sqlalchemy import text

from services.database.session_manager import get_session
from shared.config import settings
from shared.logger import getLogger
from shared.time import now_iso

from .utils import write_yaml


logger = getLogger(__name__)
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


async def _fetch_rows(query: str) -> list[dict[str, Any]]:
    """
    Generic helper to execute a read-only query and return a list of dictionaries.
    Reduces boilerplate for snapshot fetching.
    """
    async with get_session() as session:
        result = await session.execute(text(query))
        return [dict(row._mapping) for row in result]


# ID: 0e4f98b0-6132-435f-b463-9f27c447302a
async def fetch_capabilities() -> list[dict[str, Any]]:
    """Reads all capabilities from the database, ordered consistently."""
    return await _fetch_rows(
        "SELECT id, name, objective, owner, domain, tags, status "
        "FROM core.capabilities ORDER BY lower(domain), lower(name), id"
    )


# ID: 03445002-3060-4d3f-bc0b-27c6ccdc2fe9
async def fetch_symbols() -> list[dict[str, Any]]:
    """Reads all symbols from the database, ordered consistently."""
    return await _fetch_rows(
        "SELECT id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state "
        "FROM core.symbols ORDER BY fingerprint, id"
    )


# ID: 323d778b-4ed7-4d65-9d8d-9077fb880bb9
async def fetch_links() -> list[dict[str, Any]]:
    """Reads all symbol-capability links from the database, ordered consistently."""
    rows = await _fetch_rows(
        "SELECT symbol_id, capability_id, confidence, source, verified "
        "FROM core.symbol_capability_links "
        "ORDER BY capability_id, symbol_id, source"
    )
    # Decimal to float conversion for YAML serialization
    for r in rows:
        if "confidence" in r and r["confidence"] is not None:
            r["confidence"] = float(r["confidence"])
    return rows


# ID: 9f94dca6-1d04-41db-8970-b09fdc803222
async def fetch_northstar() -> list[dict[str, Any]]:
    """Reads the current North Star mission from the database."""
    return await _fetch_rows(
        "SELECT id, mission FROM core.northstar ORDER BY updated_at DESC LIMIT 1"
    )


# ID: dee34d49-638d-41ce-9f29-6941f5d90706
async def run_snapshot(env: str | None, note: str | None) -> None:
    """Exports database state to YAML files in the mind_export directory.

    Args:
        env: Environment name (e.g., 'dev'), defaults to 'dev'.
        note: Optional note for the snapshot.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    exported_at = now_iso()
    who = getpass.getuser()
    env = env or "dev"

    logger.info("Creating a new snapshot of the database in '%s'...", EXPORT_DIR)

    # Fetch all data
    caps, syms, links, north = await asyncio.gather(
        fetch_capabilities(), fetch_symbols(), fetch_links(), fetch_northstar()
    )

    # Write YAML files and collect digests
    snapshots = [
        ("capabilities.yaml", caps),
        ("symbols.yaml", syms),
        ("links.yaml", links),
        ("northstar.yaml", north),
    ]

    digests = [
        (filename, write_yaml(EXPORT_DIR / filename, data, exported_at))
        for filename, data in snapshots
    ]

    # Record in database
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    "INSERT INTO core.export_manifests (who, environment, notes) "
                    "VALUES (:who, :env, :note) RETURNING id"
                ),
                {"who": who, "env": env, "note": note},
            )
            manifest_id = result.scalar_one()

            for relpath, sha in digests:
                await session.execute(
                    text(
                        """
                        INSERT INTO core.export_digests (path, sha256, manifest_id)
                        VALUES (:path, :sha, :manifest_id)
                        ON CONFLICT (path) DO UPDATE SET
                          sha256 = EXCLUDED.sha256,
                          manifest_id = EXCLUDED.manifest_id,
                          exported_at = NOW()
                        """
                    ),
                    {
                        "path": str(
                            EXPORT_DIR.relative_to(settings.REPO_PATH) / relpath
                        ),
                        "sha": sha,
                        "manifest_id": manifest_id,
                    },
                )

    logger.info("Snapshot complete.")
    for filename, sha in digests:
        logger.debug("Wrote '{filename}' with digest: %s", sha)
