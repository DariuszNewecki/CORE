import asyncio
import ast
import re
import hashlib
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# FILES TO SCAN
FILES_TO_FIX = [
    "src/features/self_healing/header_service.py",
    "src/features/self_healing/sync_vectors.py",
    "src/shared/ast_utility.py",
    "src/body/cli/commands/develop.py"
]

# CAPABILITY MAPPING (Flexible matching)
# If the symbol is "HeaderService.fix", we look for that key.
# If not found, we look for "HeaderService".
CAPABILITY_MAP = {
    # Header Service
    "HeaderService": "self_healing.header_service.fix",
    "HeaderService.fix": "self_healing.header_service.fix",
    "HeaderService.fix_all": "self_healing.headers.fix_all",
    
    # Vector Sync
    "main_sync": "self_healing.vectors.sync",
    
    # AST Utility
    "FunctionCallVisitor": "ast.analysis.extract_calls",
    "FunctionCallVisitor.unique_calls": "ast.analysis.extract_calls",
    
    # CLI Commands
    "feature": "cli.develop.execute",
    "info": "cli.develop.execute",
    "fix": "cli.develop.execute",
    "test": "cli.develop.execute",
    "refactor": "cli.develop.refactor"
}

class SymbolVisitor(ast.NodeVisitor):
    def __init__(self, lines):
        self.lines = lines
        self.found_symbols = [] # List of (uuid, name, qualname, kind)
        self.class_stack = []

    def _find_id_for_node(self, node):
        # Look at lines preceding the node definition
        start_line = node.lineno - 1 # 0-indexed
        
        # Scan backwards up to 5 lines to skip decorators
        for i in range(1, 6):
            idx = start_line - i
            if idx < 0: break
            line = self.lines[idx].strip()
            
            # Match ID
            match = re.match(r"^# ID: ([a-f0-9\-]+)", line)
            if match:
                return match.group(1)
            
            # If empty or decorator, keep going. If code, stop.
            if not line or line.startswith("@"):
                continue
            break
        return None

    def visit_ClassDef(self, node):
        uuid = self._find_id_for_node(node)
        qualname = node.name
        if self.class_stack:
            qualname = f"{self.class_stack[-1]}.{node.name}"
        
        if uuid:
            self.found_symbols.append((uuid, node.name, qualname, "class"))
        
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node):
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_func(node)

    def _handle_func(self, node):
        uuid = self._find_id_for_node(node)
        kind = "method" if self.class_stack else "function"
        qualname = node.name
        if self.class_stack:
            qualname = f"{self.class_stack[-1]}.{node.name}"
            
        if uuid:
            self.found_symbols.append((uuid, node.name, qualname, kind))
            
        self.generic_visit(node)

async def main():
    print("🧠 Starting AST-Aware Smart Sync...")
    
    async with get_session() as session:
        async with session.begin():
            for rel_path in FILES_TO_FIX:
                path = Path(settings.REPO_PATH) / rel_path
                if not path.exists():
                    continue
                
                print(f"📂 Scanning {rel_path}...")
                content = path.read_text()
                tree = ast.parse(content)
                lines = content.splitlines()
                
                visitor = SymbolVisitor(lines)
                visitor.visit(tree)
                
                for uuid, name, qualname, kind in visitor.found_symbols:
                    # Determine Capability
                    cap_name = CAPABILITY_MAP.get(qualname)
                    if not cap_name:
                        # Fallback: Try simple name (e.g., map 'HeaderService' for 'HeaderService.fix')
                        cap_name = CAPABILITY_MAP.get(name)
                    
                    if not cap_name:
                        print(f"   ⚠️ Skipping {qualname} (No capability mapped)")
                        continue

                    print(f"   ✨ Fixing {qualname}...")
                    print(f"      -> UUID: {uuid}")
                    print(f"      -> Cap:  {cap_name}")

                    # 1. Upsert Symbol (With Correct Qualname!)
                    symbol_path = f"{rel_path}:{qualname}"
                    fake_hash = hashlib.sha256(qualname.encode()).hexdigest()
                    
                    # Clean old incorrect entries for this ID
                    await session.execute(text("DELETE FROM core.symbols WHERE id = :id"), {"id": uuid})
                    
                    await session.execute(text("""
                        INSERT INTO core.symbols 
                        (id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public)
                        VALUES (:id, :path, :mod, :qname, :kind, 'smart_sync', :fp, 'verified', true)
                        ON CONFLICT (id) DO UPDATE SET
                            symbol_path = :path,
                            qualname = :qname,
                            updated_at = now()
                    """), {
                        "id": uuid,
                        "path": symbol_path,
                        "mod": rel_path,
                        "qname": qualname,
                        "kind": kind,
                        "fp": fake_hash
                    })

                    # 2. Ensure Capability Exists
                    domain = cap_name.split('.')[0]
                    await session.execute(text("""
                        INSERT INTO core.capabilities (name, domain, title, owner, status, tags)
                        VALUES (:name, :domain, :name, 'system', 'Active', '[]'::jsonb)
                        ON CONFLICT (domain, name) DO NOTHING
                    """), {"name": cap_name, "domain": domain})

                    # 3. Link
                    res = await session.execute(text("SELECT id FROM core.capabilities WHERE name = :n"), {"n": cap_name})
                    cap_id = res.scalar()
                    
                    if cap_id:
                        await session.execute(text("""
                            INSERT INTO core.symbol_capability_links 
                            (symbol_id, capability_id, confidence, source, verified)
                            VALUES (:sid, :cid, 1.0, 'manual', true)
                            ON CONFLICT (symbol_id, capability_id, source) DO NOTHING
                        """), {"sid": uuid, "cid": cap_id})

    print("✅ Smart Sync Complete.")

if __name__ == "__main__":
    asyncio.run(main())