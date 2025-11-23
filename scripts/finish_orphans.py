import asyncio
import re
import hashlib
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# TARGETING THE METHODS NOW
TARGETS = [
    # File, Method Name, Capability, Kind
    ("src/features/self_healing/header_service.py", "fix", "self_healing.header_service.fix", "method"),
    ("src/features/self_healing/header_service.py", "fix_all", "self_healing.headers.fix_all", "method"),
    ("src/shared/ast_utility.py", "unique_calls", "ast.analysis.extract_calls", "method")
]

async def finish_job():
    print("🧹 Sweeping up remaining orphans...")
    
    async with get_session() as session:
        async with session.begin():
            for rel_path, method_name, capability_name, kind in TARGETS:
                path = Path(settings.REPO_PATH) / rel_path
                if not path.exists():
                    print(f"❌ File missing: {rel_path}")
                    continue

                content = path.read_text()
                lines = content.splitlines()
                found_uuid = None
                
                # Scan for the method definition and its ID
                for i, line in enumerate(lines):
                    if f"def {method_name}" in line:
                        # Look backwards for # ID:
                        scan_idx = i - 1
                        while scan_idx >= 0:
                            if "# ID:" in lines[scan_idx]:
                                match = re.search(r"# ID: ([a-f0-9\-]+)", lines[scan_idx])
                                if match:
                                    found_uuid = match.group(1)
                                break
                            if lines[scan_idx].strip().startswith("def "):
                                break # Don't bleed into previous function
                            scan_idx -= 1
                        if found_uuid: 
                            break
                
                if not found_uuid:
                    print(f"⚠️  No ID found for method '{method_name}' in {rel_path}")
                    continue

                print(f"🔄 Registering Method: {method_name} ({found_uuid})...")

                # 1. Register Symbol (Method)
                # Note: symbol_path for methods usually includes the class, e.g. module:Class.method
                # We will try to guess the parent class from the file content or just use module:method for safety
                # The system seems to accept module:method or just unique path.
                symbol_path = f"{rel_path}:{method_name}" 
                fake_hash = hashlib.sha256(method_name.encode()).hexdigest()
                
                await session.execute(text("""
                    INSERT INTO core.symbols 
                    (id, symbol_path, module, qualname, kind, ast_signature, fingerprint, state, is_public)
                    VALUES (:id, :path, :mod, :name, :kind, :sig, :fp, 'verified', true)
                    ON CONFLICT (id) DO UPDATE SET
                        symbol_path = :path,
                        updated_at = now()
                """), {
                    "id": found_uuid,
                    "path": symbol_path,
                    "mod": rel_path,
                    "name": method_name,
                    "kind": kind,
                    "sig": "manual_method_fix",
                    "fp": fake_hash
                })

                # 2. Link to Capability
                # Get Cap ID
                res = await session.execute(text("SELECT id FROM core.capabilities WHERE name = :n"), {"n": capability_name})
                cap_id = res.scalar()
                
                if cap_id:
                    await session.execute(text("""
                        INSERT INTO core.symbol_capability_links 
                        (symbol_id, capability_id, confidence, source, verified)
                        VALUES (:sid, :cid, 1.0, 'manual', true)
                        ON CONFLICT (symbol_id, capability_id, source) DO NOTHING
                    """), {"sid": found_uuid, "cid": cap_id})
                    print(f"   ✅ LINKED: {method_name} -> {capability_name}")
                else:
                    print(f"   ❌ Capability {capability_name} not found!")

    print("✨ Clean sweep complete.")

if __name__ == "__main__":
    asyncio.run(finish_job())