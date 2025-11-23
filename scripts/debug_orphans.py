import asyncio
import re
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# Target: The specific symbol failing the audit
TARGET_FILE = "src/body/cli/commands/develop.py"
TARGET_SYMBOL = "feature"

async def diagnose():
    print(f"🔍 DIAGNOSTIC: Tracing symbol '{TARGET_SYMBOL}'...")
    
    # 1. CHECK DISK
    path = Path(settings.REPO_PATH) / TARGET_FILE
    if not path.exists():
        print(f"❌ File not found: {path}")
        return

    content = path.read_text()
    lines = content.splitlines()
    file_uuid = None
    
    # Simple parser to find the ID above the symbol
    for i, line in enumerate(lines):
        if f"def {TARGET_SYMBOL}" in line or f"async def {TARGET_SYMBOL}" in line:
            # Look backwards for ID
            if i > 0 and "# ID:" in lines[i-1]:
                match = re.search(r"# ID: ([a-f0-9\-]+)", lines[i-1])
                if match:
                    file_uuid = match.group(1)
                    print(f"✅ DISK: Found Tag in file: {file_uuid}")
            break
    
    if not file_uuid:
        print("❌ DISK: No # ID: tag found in file near definition.")
        return

    # 2. CHECK DATABASE
    async with get_session() as session:
        # A. Check core.symbols
        print(f"📊 DB: Checking core.symbols for {file_uuid}...")
        result = await session.execute(text(
            "SELECT id, symbol_path, state FROM core.symbols WHERE id = :id"
        ), {"id": file_uuid})
        symbol_row = result.fetchone()
        
        if symbol_row:
            print(f"   ✅ Found in core.symbols: {symbol_row.symbol_path} (State: {symbol_row.state})")
        else:
            print("   ❌ NOT FOUND in core.symbols. This is the root cause.")
            print("      -> The system hasn't scanned this file since the tag was added.")
            print("      -> Fix: Need to re-run symbol discovery (manage define-symbols).")

        # B. Check core.symbol_capability_links
        print(f"🔗 DB: Checking core.symbol_capability_links for {file_uuid}...")
        result = await session.execute(text(
            "SELECT capability_id, source FROM core.symbol_capability_links WHERE symbol_id = :id"
        ), {"id": file_uuid})
        link_row = result.fetchone()
        
        if link_row:
            print(f"   ✅ Found Link to Capability: {link_row.capability_id} (Source: {link_row.source})")
        else:
            print("   ❌ NOT FOUND in core.symbol_capability_links.")
            if symbol_row:
                print("      -> The symbol exists, but the link is missing.")
                print("      -> Cause: Migration skipped it or Tagger failed to write link.")
        
        # C. Check View Definition (Sanity Check)
        print("👀 DB: Verifying v_orphan_symbols definition...")
        result = await session.execute(text(
            "SELECT definition FROM pg_views WHERE viewname = 'v_orphan_symbols' AND schemaname = 'core'"
        ))
        view_def = result.scalar()
        if "entry_points" in view_def:
            print("   ❌ STALE VIEW: v_orphan_symbols is still looking for 'entry_points' array!")
        elif "symbol_capability_links" in view_def:
            print("   ✅ View is updated (looks at links table).")
        else:
            print(f"   ⚠️ Unknown View Definition: {view_def[:50]}...")

if __name__ == "__main__":
    asyncio.run(diagnose())