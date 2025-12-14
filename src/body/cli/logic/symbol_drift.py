# src/body/cli/logic/symbol_drift.py

"""
Implements the `inspect symbol-drift` command, a diagnostic tool to detect
discrepancies between symbols on the filesystem and those in the database.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from features.introspection.sync_service import SymbolScanner
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


async def _run_drift_analysis():
    """
    The core logic that scans source, queries the DB, and compares the results.
    """
    logger.info("Running Symbol Drift Analysis...")
    logger.info("Scanning 'src/' directory for all public symbols...")
    scanner = SymbolScanner()
    code_symbols = await asyncio.to_thread(scanner.scan)
    code_symbol_paths = {s["symbol_path"] for s in code_symbols}
    logger.info("Found %s symbols in source code.", len(code_symbol_paths))
    logger.info("Querying database for all registered symbols...")
    db_symbol_paths = set()
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT symbol_path FROM core.symbols"))
            db_symbol_paths = {row[0] for row in result}
        logger.info("Found %s symbols in the database.", len(db_symbol_paths))
    except Exception as e:
        logger.error("Database query failed: %s", e)
        logger.info("Please ensure your database is running and accessible.")
        return
    ghost_symbols_in_db = sorted(list(db_symbol_paths - code_symbol_paths))
    new_symbols_in_code = sorted(list(code_symbol_paths - db_symbol_paths))
    logger.info("--- Analysis Complete ---")
    if not ghost_symbols_in_db and (not new_symbols_in_code):
        logger.info(
            "No drift detected. The database is perfectly synchronized with the source code."
        )
        return
    if ghost_symbols_in_db:
        logger.warning("Found %s Ghost Symbols in Database", len(ghost_symbols_in_db))
        logger.warning(
            "These symbols exist in the DB but NOT in the source code. They should be pruned."
        )
        for symbol in ghost_symbols_in_db:
            logger.warning("  - %s", symbol)
        logger.info(
            "Diagnosis: The `sync-knowledge` command is failing to delete obsolete symbols from the database."
        )
    if new_symbols_in_code:
        logger.info("Found %s New Symbols in Source Code", len(new_symbols_in_code))
        logger.info(
            "These symbols exist in the code but NOT in the DB. They need to be synchronized."
        )
        for symbol in new_symbols_in_code:
            logger.info("  - %s", symbol)
    logger.info(
        "Next Step: This report confirms a bug in the sync logic. Please proceed with fixing the `run_sync_with_db` function."
    )


# ID: 2ff57ea1-2b62-4c75-9586-10219c51ea13
def inspect_symbol_drift():
    """Synchronous Typer wrapper for the async drift analysis logic."""
    asyncio.run(_run_drift_analysis())
