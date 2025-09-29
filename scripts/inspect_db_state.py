#!/usr/bin/env python3
# scripts/inspect_db_state.py
"""
Quick script to inspect the current state of CORE database tables
and identify which ones have data vs which are empty.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path so we can import CORE modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# --- FIX: Use the correct function name 'get_session' ---
from services.database.session_manager import get_session
from sqlalchemy import text


async def inspect_database():
    """Check the state of all CORE database tables."""
    
    # List of tables that correspond to the deleted YAML files
    tables_to_check = [
        'cli_commands',
        'llm_resources',
        'cognitive_roles',
    ]
    
    # --- FIX: Use the correct function name 'get_session' ---
    async with get_session() as session:
        print("CORE Operational Knowledge Inspection")
        print("=" * 50)
        print("Verifying that legacy YAML data now lives in the database...")
        
        all_found = True
        for table in tables_to_check:
            try:
                # Get row count
                result = await session.execute(text(f"SELECT COUNT(*) FROM core.{table}"))
                count = result.scalar_one_or_none() or 0
                
                if count > 0:
                    status = f"✅ POPULATED ({count} rows)"
                else:
                    status = "❌ EMPTY"
                    all_found = False
                    
            except Exception as e:
                status = f"ERROR: {e}"
                all_found = False
            
            print(f"  - Table `core.{table}`: {status}")
        
        print("-" * 50)
        if all_found:
            print("✅ Success: All operational knowledge tables are populated.")
            print("You can safely proceed with the removal of the legacy YAML files.")
        else:
            print("❌ Warning: One or more operational tables are empty.")
            print("It may be necessary to run the migration or sync commands.")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(inspect_database())