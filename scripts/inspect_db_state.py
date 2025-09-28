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

from services.database.session_manager import get_async_session
from sqlalchemy import text


async def inspect_database():
    """Check the state of all CORE database tables."""
    
    # List of tables we expect to exist based on the migrations
    tables_to_check = [
        'proposals',
        'proposal_signatures', 
        'audit_runs',
        'symbols',
        'capabilities',
        'symbol_capabilities',
        'domains',
        'llm_resources',
        'cognitive_roles',
        'cli_commands',
        'runtime_services'
    ]
    
    async with get_async_session() as session:
        print("CORE Database State Inspection")
        print("=" * 50)
        
        for table in tables_to_check:
            try:
                # Get row count
                result = await session.execute(text(f"SELECT COUNT(*) FROM core.{table}"))
                count = result.scalar()
                
                # Get a sample row if data exists
                if count > 0:
                    sample_result = await session.execute(text(f"SELECT * FROM core.{table} LIMIT 1"))
                    sample_row = sample_result.fetchone()
                    columns = list(sample_row._mapping.keys()) if sample_row else []
                    status = f"{count} rows - Columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
                else:
                    status = "EMPTY"
                    
            except Exception as e:
                status = f"ERROR: {e}"
            
            print(f"  {table:20} {status}")
        
        print("\n" + "=" * 50)
        
        # Also check if there are any views
        try:
            views_result = await session.execute(text("""
                SELECT table_name FROM information_schema.views 
                WHERE table_schema = 'core'
            """))
            views = [row[0] for row in views_result.fetchall()]
            if views:
                print(f"Database Views: {', '.join(views)}")
            else:
                print("No views found")
        except Exception as e:
            print(f"Could not check views: {e}")


if __name__ == "__main__":
    asyncio.run(inspect_database())