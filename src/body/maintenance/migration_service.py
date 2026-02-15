# src/body/maintenance/migration_service.py

"""
Provides a one-time migration service to populate the SSOT database from legacy
file-based sources.

MOVED: From features/maintenance to body/maintenance (Constitutional Rebirth Wave 1).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


async def _migrate_capabilities_from_manifest() -> list[dict[str, Any]]:
    """Loads capabilities from the legacy project_manifest.yaml file."""
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
    # NOTE: Introspection still lives in features/ for this sub-step
    from body.introspection.sync_service import SymbolScanner

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
                "ast_signature": symbol_data.get("ast_signature", "pending"),
                "fingerprint": symbol_data["fingerprint"],
                "state": symbol_data.get("state", "discovered"),
                "symbol_path": symbol_data["symbol_path"],
            }
        )
    return migrated_syms


# ID: 7038f63f-b52c-48ea-a03d-5c18f4f38129
async def run_ssot_migration(session: AsyncSession, dry_run: bool):
    """
    Orchestrates the full one-time migration from files to the SSOT database.
    """
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

    async with session.begin():
        await session.execute(text("DELETE FROM core.symbol_capability_links;"))
        await session.execute(text("DELETE FROM core.symbols;"))
        await session.execute(text("DELETE FROM core.capabilities;"))

        if capabilities:
            await session.execute(
                text(
                    "INSERT INTO core.capabilities (id, name, title, objective, owner, domain, tags, status) VALUES (:id, :name, :title, :objective, :owner, :domain, :tags, :status)"
                ),
                capabilities,
            )

        if symbols:
            insert_stmt = text(
                "INSERT INTO core.symbols (id, module, qualname, kind, ast_signature, fingerprint, state, symbol_path) VALUES (:id, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :symbol_path) ON CONFLICT (symbol_path) DO NOTHING;"
            )
            for symbol in symbols:
                await session.execute(insert_stmt, symbol)

    logger.info("✅ One-time migration complete.")
