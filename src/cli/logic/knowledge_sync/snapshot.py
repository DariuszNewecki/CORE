# src/cli/logic/knowledge_sync/snapshot.py
"""
Handles snapshot operations to export database state to YAML files for the CORE Working Mind.
"""

from __future__ import annotations

import asyncio
import getpass
from typing import Any, List

from rich.console import Console
from services.database.session_manager import get_session
from shared.config import settings
from shared.time import now_iso
from sqlalchemy import text

from .utils import write_yaml

console = Console()
EXPORT_DIR = settings.REPO_PATH / ".intent" / "mind_export"


# ID: f5b271c7-012a-4ba6-b75c-27308e3056bb
async def fetch_capabilities() -> List[dict[str, Any]]:
    """Reads all capabilities from the database, ordered consistently.

    Returns:
        List of capability dictionaries.
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, name, objective, owner, domain, tags, status "
                "FROM core.capabilities ORDER BY lower(domain), lower(name), id"
            )
        )
        return [dict(row._mapping) for row in result]


# ID: 7ac0e4a7-11b9-49c5-8d70-6f1a99749ee8
async def fetch_symbols() -> List[dict[str, Any]]:
    """Reads all symbols from the database, ordered consistently.

    Returns:
        List of symbol dictionaries.
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, module, qualname, kind, ast_signature, fingerprint, state "
                "FROM core.symbols ORDER BY fingerprint, id"
            )
        )
        return [dict(row._mapping) for row in result]


# ID: b48a1aa4-1887-4cfe-8954-2ae4ce86f1a5
async def fetch_links() -> List[dict[str, Any]]:
    """Reads all symbol-capability links from the database, ordered consistently.

    Returns:
        List of link dictionaries.
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT symbol_id, capability_id, confidence, source, verified "
                "FROM core.symbol_capability_links "
                "ORDER BY capability_id, symbol_id, source"
            )
        )
        rows = [dict(row._mapping) for row in result]
        for r in rows:
            if "confidence" in r and r["confidence"] is not None:
                r["confidence"] = float(r["confidence"])
        return rows


# ID: 1997db61-1fa0-4cef-b57d-c538fd3fa7c2
async def fetch_northstar() -> List[dict[str, Any]]:
    """Reads the current North Star mission from the database.

    Returns:
        List containing the North Star dictionary.
    """
    async with get_session() as session:
        result = await session.execute(
            text(
                "SELECT id, mission FROM core.northstar "
                "ORDER BY updated_at DESC LIMIT 1"
            )
        )
        return [dict(row._mapping) for row in result]


# ID: 4c9c59a9-0612-40f2-99ac-957e93be77e3
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

    console.print(f"📸 Creating a new snapshot of the database in '{EXPORT_DIR}'...")

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

    console.print("[bold green]✅ Snapshot complete.[/bold green]")
    for filename, sha in digests:
        console.print(f"  - Wrote '{filename}' with digest: {sha}")
