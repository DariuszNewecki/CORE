# src/features/maintenance/migration_service.py
"""
Provides a one-time migration service to populate the SSOT database from legacy
file-based sources (.intent/mind/project_manifest.yaml and AST scan).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Dict, List

import yaml
from rich.console import Console
from services.database.session_manager import get_session
from shared.config import settings
from sqlalchemy import text

console = Console()


async def _migrate_capabilities_from_manifest() -> List[Dict[str, Any]]:
    """Loads capabilities from the legacy project_manifest.yaml file, ensuring uniqueness."""
    manifest_path = settings.get_path("mind.project_manifest")
    if not manifest_path.exists():
        console.print(
            "[yellow]Warning: project_manifest.yaml not found. No capabilities to migrate.[/yellow]"
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


async def _migrate_symbols_from_ast() -> List[Dict[str, Any]]:
    """Scans the codebase using SymbolScanner to populate the symbols table."""
    from features.introspection.sync_service import SymbolScanner

    scanner = SymbolScanner()
    code_symbols = await asyncio.to_thread(scanner.scan)

    migrated_syms = []
    for symbol_data in code_symbols:
        migrated_syms.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, symbol_data["symbol_path"]),
                "uuid": symbol_data["uuid"],
                "module": symbol_data["file_path"],
                "qualname": symbol_data["symbol_path"].split("::")[-1],
                "kind": (
                    "function" if "Function" in symbol_data.get("type", "") else "class"
                ),
                "ast_signature": "TBD",
                "fingerprint": symbol_data["structural_hash"],
                "state": "discovered",
                "symbol_path": symbol_data[
                    "symbol_path"
                ],  # Ensure the true identifier is present
            }
        )
    return migrated_syms


# ID: cd2c3cf5-54ec-493c-b11f-d8bb6eae7a0f
async def run_ssot_migration(dry_run: bool):
    """Orchestrates the full one-time migration from files to the SSOT database."""
    console.print(
        "🚀 Starting one-time migration of knowledge from files to database..."
    )

    capabilities = await _migrate_capabilities_from_manifest()
    symbols = await _migrate_symbols_from_ast()

    if dry_run:
        console.print(
            "[bold yellow]-- DRY RUN: The following actions would be taken --[/bold yellow]"
        )
        console.print(
            f"  - Insert {len(capabilities)} unique capabilities from project_manifest.yaml."
        )
        console.print(f"  - Insert {len(symbols)} symbols from source code scan.")
        return

    async with get_session() as session:
        async with session.begin():
            console.print("  -> Deleting existing data from tables...")
            await session.execute(text("DELETE FROM core.symbol_capability_links;"))
            await session.execute(text("DELETE FROM core.symbols;"))
            await session.execute(text("DELETE FROM core.capabilities;"))

            console.print(f"  -> Inserting {len(capabilities)} capabilities...")
            if capabilities:
                await session.execute(
                    text(
                        """
                    INSERT INTO core.capabilities (id, name, title, objective, owner, domain, tags, status)
                    VALUES (:id, :name, :title, :objective, :owner, :domain, :tags, :status)
                """
                    ),
                    capabilities,
                )

            console.print(f"  -> Inserting {len(symbols)} symbols...")
            if symbols:
                # Insert symbols one by one to handle potential duplicates gracefully if any slip through
                insert_stmt = text(
                    """
                    INSERT INTO core.symbols (id, uuid, module, qualname, kind, ast_signature, fingerprint, state, symbol_path)
                    VALUES (:id, :uuid, :module, :qualname, :kind, :ast_signature, :fingerprint, :state, :symbol_path)
                    ON CONFLICT (symbol_path) DO NOTHING;
                """
                )
                for symbol in symbols:
                    await session.execute(insert_stmt, symbol)

    console.print("[bold green]✅ One-time migration complete.[/bold green]")
    console.print(
        "Run 'core-admin mind snapshot' to create the first export from the database."
    )
