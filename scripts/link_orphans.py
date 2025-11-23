import asyncio
import re
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# Files to fix
FILES = [
    "src/body/cli/commands/develop.py",
    "src/body/services/crate_creation_service.py",
    "src/features/self_healing/header_service.py",
    "src/features/self_healing/sync_vectors.py",
    "src/shared/ast_utility.py"
]

# Capability Mapping
MAPPING = {
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

async def link_orphans():
    print("🔗 Linking existing tags to capabilities...")
    
    async with get_session() as session:
        async with session.begin():
            for rel_path in FILES:
                path = Path(settings.REPO_PATH) / rel_path
                if not path.exists():
                    continue
                
                content = path.read_text()
                lines = content.splitlines()
                current_id = None
                
                for line in lines:
                    # 1. Find ID
                    id_match = re.match(r"^\s*# ID: ([a-f0-9\-]+)", line)
                    if id_match:
                        current_id = id_match.group(1)
                        continue
                    
                    # 2. Find Definition
                    def_match = re.match(r"^\s*(async\s+)?(def|class)\s+([a-zA-Z0-9_]+)", line)
                    if def_match and current_id:
                        name = def_match.group(3)
                        
                        # 3. Resolve Capability
                        cap_name = MAPPING.get(name)
                        if not cap_name:
                            # Method check
                            for k, v in MAPPING.items():
                                if k.endswith(f".{name}"):
                                    cap_name = v
                                    break
                        
                        if cap_name:
                            # 4. INSERT LINK (Normalized Schema)
                            print(f"   -> Linking {name} ({current_id}) to {cap_name}")
                            
                            # Get Cap ID
                            res = await session.execute(text("SELECT id FROM core.capabilities WHERE name = :n"), {"n": cap_name})
                            cap_id = res.scalar()
                            
                            if cap_id:
                                await session.execute(text("""
                                    INSERT INTO core.symbol_capability_links 
                                    (symbol_id, capability_id, confidence, source, verified)
                                    VALUES (:sid, :cid, 1.0, 'manual', true)
                                    ON CONFLICT (symbol_id, capability_id, source) DO NOTHING
                                """), {"sid": current_id, "cid": cap_id})
                            else:
                                print(f"      ⚠️ Capability {cap_name} not found in DB!")
                                
                        current_id = None

if __name__ == "__main__":
    asyncio.run(link_orphans())