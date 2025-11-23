import asyncio
import re
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session

# Paths to the files that were modified but likely failed to sync to DB
FILES_TO_SCAN = [
    "src/body/cli/commands/develop.py",
    "src/body/services/crate_creation_service.py",
    "src/features/self_healing/header_service.py",
    "src/features/self_healing/sync_vectors.py",
    "src/shared/ast_utility.py"
]

# Map symbol names to the capabilities suggested in your logs
# This ensures we assign them to the right place.
SYMBOL_CAPABILITY_MAP = {
    "feature": "cli.develop.execute",
    "info": "cli.develop.execute",
    "fix": "cli.develop.execute",
    "test": "cli.develop.execute",
    "refactor": "cli.develop.refactor",
    "create_crate_from_generation_result": "crate.create.from_generation",
    "HeaderService.fix": "self_healing.header_service.fix",
    "HeaderService.fix_all": "self_healing.headers.fix_all",
    "main_sync": "self_healing.vectors.sync",
    "FunctionCallVisitor.unique_calls": "ast.analysis.extract_calls"
}

async def repair():
    print("🔧 Starting Orphan Repair...")
    
    async with get_session() as session:
        for file_path_str in FILES_TO_SCAN:
            path = Path(file_path_str)
            if not path.exists():
                print(f"❌ File not found: {path}")
                continue

            print(f"📂 Scanning {path.name}...")
            content = path.read_text()
            lines = content.splitlines()
            
            # Regex to find ID preceding a definition
            # Looks for: # ID: <uuid> \n [decorators] \n def <name>
            # We scan line by line to handle this simply
            
            current_id = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Detect ID
                id_match = re.match(r"^# ID: ([a-f0-9\-]+)", line)
                if id_match:
                    current_id = id_match.group(1)
                    continue
                    
                # Detect definition
                def_match = re.match(r"^(async\s+)?(def|class)\s+([a-zA-Z0-9_]+)", line)
                if def_match and current_id:
                    symbol_name = def_match.group(3)
                    
                    # Handle method names like Class.method if possible, 
                    # strictly speaking we just match the simple name here 
                    # and lookup in our map.
                    
                    # Check if this symbol is in our repair map
                    # We try exact match first, then fuzzy for methods
                    target_cap = SYMBOL_CAPABILITY_MAP.get(symbol_name)
                    
                    if not target_cap:
                        # Try to find composite key (e.g. HeaderService.fix)
                        for key in SYMBOL_CAPABILITY_MAP:
                            if key.endswith(f".{symbol_name}"):
                                target_cap = SYMBOL_CAPABILITY_MAP[key]
                                break
                    
                    if target_cap:
                        print(f"   MATCH: {symbol_name} -> {target_cap} (ID: {current_id})")
                        
                        # Force update DB
                        domain = target_cap.split('.')[0]
                        
                        await session.execute(text("""
                            INSERT INTO core.capabilities (name, domain, title, owner, entry_points, status, tags)
                            VALUES (:name, :domain, :name, 'system', ARRAY[:uuid]::uuid[], 'Active', '[]'::jsonb)
                            ON CONFLICT (domain, name)
                            DO UPDATE SET
                                entry_points = CASE 
                                    WHEN NOT (:uuid = ANY(core.capabilities.entry_points)) 
                                    THEN array_append(core.capabilities.entry_points, :uuid)
                                    ELSE core.capabilities.entry_points
                                END,
                                updated_at = now();
                        """), {"name": target_cap, "domain": domain, "uuid": current_id})
                        print(f"     ✅ Registered in DB.")
                    
                    # Reset ID after use
                    current_id = None
                
                # Reset ID if we hit a blank line or something else that breaks the chain
                if not line and not current_id:
                    pass

        await session.commit()
        print("💾 Transaction committed.")

if __name__ == "__main__":
    try:
        asyncio.run(repair())
    except Exception as e:
        print(f"❌ Critical Error: {e}")