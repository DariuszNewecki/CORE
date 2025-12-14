# src/features/maintenance/migration_service.py

"""
Provides a one-time migration service to populate the SSOT database from legacy
file-based sources (.intent/mind/project_manifest.yaml and AST scan).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import yaml
from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


async def _migrate_capabilities_from_manifest() -> list[dict[str, Any]]:
    """Loads capabilities from the legacy project_manifest.yaml file, ensuring uniqueness."""
    manifest_path = settings.get_path("mind.knowledge.project_manifest")
    if not manifest_path.exists():
        logger.info(
            "Warning: project_manifest.yaml not found. No capabilities to migrate."
        )
        return []
    content = yaml.safe_load(manifest_path.read_text("utf-8")) or {}
    capability_keys = content.get("capabilities", [])
    unique_clean_keys = set()
    for key in capability_keys:
        clean_key = key.replace("`", "").strip()
        if clean_key:
            unique_clean_keys.add(clean_key)
    migrated_caps = []
    for clean_key in sorted(list(unique_clean_keys)):
        domain = clean_key.split(".")[0] if "." in clean_key else "general"
        title = clean_key.split(".")[-1].replace("_", " ").capitalize()
        migrated_caps.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, clean_key),
                "name": clean_key,
                "title": title,
                "objective": "Migrated from legacy project_manifest.yaml.",
                "owner": "system",
                "domain": domain,
                "tags": json.dumps([]),
                "status": "Active",
            }
        )
    return migrated_caps


async def _migrate_symbols_from_ast() -> list[dict[str, Any]]:
    """Scans the codebase using SymbolScanner to populate the symbols table."""
    from features.introspection.sync_service import SymbolScanner

    scanner = SymbolScanner()
    code_symbols = await asyncio.to_thread(scanner.scan)
    migrated_syms = []
    for symbol_data in code_symbols:
        migrated_syms.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, symbol_data["symbol_path"]),
                "module": symbol_data["module"],
                "qualname": symbol_data["qualname"],
                "kind": symbol_data["kind"],
                "ast_signature": symbol_data.get("ast_signature", "TBD"),
                "fingerprint": symbol_data["fingerprint"],
                "state": symbol_data.get("state", "discovered"),
                "symbol_path": symbol_data["symbol_path"],
            }
        )
    return migrated_syms


# ID: 7038f63f-b52c-48ea-a03d-5c18f4f38129
async def run_ssot_migration(dry_run: bool):
    """Orchestrates the full one-time migration from files to the SSOT database."""
    logger.info("Starting one-time migration of knowledge from files to database...")
    capabilities = await _migrate_capabilities_from_manifest()
    symbols = await _migrate_symbols_from_ast()
    if dry_run:
        logger.info("-- DRY RUN: The following actions would be taken --")
        logger.info(
            "  - Insert %s unique capabilities from project_manifest.yaml.",
            len(capabilities),
        )
        logger.info("  - Insert %s symbols from source code scan.", len(symbols))
        return
    async with get_session() as session:
        async with session.begin():
            logger.info("  -> Deleting existing data from tables...")
            await session.execute(text("DELETE FROM core.symbol_capability_links;"))
            await session.execute(text("DELETE FROM core.symbols;"))
            await session.execute(text("DELETE FROM core.capabilities;"))
            logger.info("  -> Inserting %s capabilities...", len(capabilities))
            if capabilities:
                await session.execute(
                    text(
                        "\n                    INSERT INTO core.capabilities (id, name, title, objective, owner, domain, tags, status)\n                    VALUES (:id, :name, :title, :objective, :owner, :domain, :tags, :status)\n                "
                    ),
                    capabilities,
                )
            logger.info("  -> Inserting %s symbols...", len(symbols))
            if symbols:
                insert_stmt = text(
                    "\n                    INSERT INTO core.symbols (id, module, qualname, kind, ast_signature, fingerprint, state, symbol_path)\n                    VALUES (:id, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :symbol_path)\n                    ON CONFLICT (symbol_path) DO NOTHING;\n                "
                )
                for symbol in symbols:
                    await session.execute(insert_stmt, symbol)
    logger.info("✅ One-time migration complete.")
    logger.info(
        "Run 'core-admin mind snapshot' to create the first export from the database."
    )
