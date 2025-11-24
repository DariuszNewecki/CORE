# scripts/register_test_gen_capabilities.py
"""
Registers the Test Generation components as official system Capabilities.
Resolves 'Orphaned logic' errors by explicitly declaring intent.
"""

import asyncio
import re
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# Map the orphaned symbols to logical Capability Keys
CAPABILITY_MAP = {
    # Code Extractor
    "src/features/self_healing/test_generation/code_extractor.py::CodeExtractor.extract": 
        "self_healing.test_gen.extract_code",
    
    # Executor
    "src/features/self_healing/test_generation/executor.py::TestExecutor.execute_test": 
        "self_healing.test_gen.execute",
    
    # Single Test Fixer
    "src/features/self_healing/test_generation/single_test_fixer.py::SingleTestFixer.fix_test": 
        "self_healing.test_gen.fix_single",
    "src/features/self_healing/test_generation/single_test_fixer.py::TestExtractor.replace_test_function": 
        "self_healing.test_gen.replace_fn",
        
    # Context Reuse
    "src/services/context/reuse.py::ReuseFinder.summarize_for_prompt": 
        "context.reuse.summarize",
        
    # Shared Utils
    "src/shared/utils/common_knowledge.py::normalize_whitespace": 
        "shared.universal.normalize_whitespace"
}

async def register():
    print("🛡️  Registering Test Generation Capabilities...")
    
    async with get_session() as session:
        async with session.begin():
            for symbol_path, cap_key in CAPABILITY_MAP.items():
                print(f"   Processing {cap_key}...")
                
                # 1. Get the Symbol ID
                result = await session.execute(
                    text("SELECT id, qualname FROM core.symbols WHERE symbol_path = :path"), 
                    {"path": symbol_path}
                )
                symbol_row = result.fetchone()
                
                if not symbol_row:
                    print(f"   ⚠️  Symbol not found in DB: {symbol_path}")
                    continue
                    
                symbol_id = str(symbol_row.id)
                qualname = symbol_row.qualname
                
                # 2. Register Capability
                domain = cap_key.split('.')[0]
                await session.execute(text("""
                    INSERT INTO core.capabilities (name, domain, title, owner, status, tags)
                    VALUES (:name, :domain, :title, 'system', 'Active', '["test-gen"]'::jsonb)
                    ON CONFLICT (domain, name) DO NOTHING
                """), {
                    "name": cap_key, 
                    "domain": domain, 
                    "title": qualname
                })
                
                # 3. Get Capability ID
                cap_res = await session.execute(
                    text("SELECT id FROM core.capabilities WHERE name = :name"),
                    {"name": cap_key}
                )
                cap_id = cap_res.scalar()
                
                # 4. Link them
                if cap_id:
                    # FIX: Changed 'manual_registration' to 'manual' to satisfy DB constraint
                    await session.execute(text("""
                        INSERT INTO core.symbol_capability_links 
                        (symbol_id, capability_id, confidence, source, verified)
                        VALUES (:sid, :cid, 1.0, 'manual', true)
                        ON CONFLICT (symbol_id, capability_id, source) DO NOTHING
                    """), {"sid": symbol_id, "cid": cap_id})
                    
                    # Update the symbol table for fast lookups
                    await session.execute(text("""
                        UPDATE core.symbols SET key = :key WHERE id = :id
                    """), {"key": cap_key, "id": symbol_id})
                    
                    print(f"   ✅ Linked: {qualname} -> {cap_key}")

    print("✨ Registration complete.")

if __name__ == "__main__":
    asyncio.run(register())