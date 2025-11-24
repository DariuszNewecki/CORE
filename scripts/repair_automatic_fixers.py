# scripts/repair_automatic_fixers.py
"""
Surgical repair to assign capability keys to the Automatic Repair fixers.
Resolves 'Orphaned logic' errors in the constitutional audit.
"""

import asyncio
import re
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# Target file containing the orphans
TARGET_FILE = "src/features/self_healing/test_generation/automatic_repair.py"

# Map class names to logical capability keys
# We derive the key from the class name: EOFSyntaxFixer -> self_healing.repair.eof_syntax
FIXER_CLASSES = [
    "QuoteFixer",
    "UnterminatedStringFixer",
    "TrailingWhitespaceFixer",
    "EmptyFunctionFixer",
    "MixedQuoteFixer",
    "TruncatedDocstringFixer",
    "EOFSyntaxFixer",
    "AutomaticRepairService"
]

async def repair():
    print(f"🔧 Repairing orphans in {TARGET_FILE}...")
    
    repo_rel_path = Path(TARGET_FILE)
    
    async with get_session() as session:
        async with session.begin():
            for class_name in FIXER_CLASSES:
                # 1. Define the capability key
                # Convert CamelCase to snake_case
                snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
                capability_key = f"self_healing.repair.{snake_name}"
                
                # 2. Update the Class symbol
                # Matches: src/.../automatic_repair.py::ClassName
                class_symbol_path = f"{TARGET_FILE}::{class_name}"
                
                print(f"   -> Assigning {class_name} to {capability_key}")
                
                await session.execute(text("""
                    UPDATE core.symbols 
                    SET key = :key, intent = 'Micro-fixer for automatic code repair', updated_at = NOW()
                    WHERE symbol_path = :path
                """), {"key": capability_key, "path": class_symbol_path})
                
                # 3. Update the 'fix' method symbol
                # Matches: src/.../automatic_repair.py::ClassName.fix
                method_symbol_path = f"{TARGET_FILE}::{class_name}.fix"
                
                await session.execute(text("""
                    UPDATE core.symbols 
                    SET key = :key, intent = 'Apply specific fix strategy', updated_at = NOW()
                    WHERE symbol_path = :path
                """), {"key": capability_key, "path": method_symbol_path})
                
                # 4. Ensure the Capability exists in the capabilities table
                await session.execute(text("""
                    INSERT INTO core.capabilities (name, domain, title, owner, status, tags)
                    VALUES (:name, 'self_healing', :title, 'system', 'Active', '["repair", "auto"]'::jsonb)
                    ON CONFLICT (domain, name) DO NOTHING
                """), {
                    "name": capability_key,
                    "title": class_name
                })

    print("✅ Repair complete. Orphans should be resolved.")

if __name__ == "__main__":
    asyncio.run(repair())