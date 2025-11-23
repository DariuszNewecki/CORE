import asyncio
import re
from pathlib import Path
from sqlalchemy import text
from services.database.session_manager import get_session
from shared.config import settings

# Comprehensive list of all symbols that tend to get orphaned
TARGETS = [
    # (File Partial Path, Symbol Name, Capability Name)
    
    # CLI Commands (develop.py)
    ("src/body/cli/commands/develop.py", "feature", "cli.develop.execute"),
    ("src/body/cli/commands/develop.py", "info", "cli.develop.execute"),
    ("src/body/cli/commands/develop.py", "fix", "cli.develop.execute"),
    ("src/body/cli/commands/develop.py", "test", "cli.develop.execute"),
    ("src/body/cli/commands/develop.py", "refactor", "cli.develop.refactor"),
    
    # Services
    ("src/body/services/crate_creation_service.py", "create_crate_from_generation_result", "crate.create.from_generation"),
    ("src/features/self_healing/sync_vectors.py", "main_sync", "self_healing.vectors.sync"),
    
    # Classes & Methods (HeaderService)
    ("src/features/self_healing/header_service.py", "HeaderService", "self_healing.header_service.fix"),
    ("src/features/self_healing/header_service.py", "fix", "self_healing.header_service.fix"),
    ("src/features/self_healing/header_service.py", "fix_all", "self_healing.headers.fix_all"),
    
    # AST Utility
    ("src/shared/ast_utility.py", "FunctionCallVisitor", "ast.analysis.extract_calls"),
    ("src/shared/ast_utility.py", "unique_calls", "ast.analysis.extract_calls")
]

async def restore():
    print("🩹 Restoring broken links...")
    
    async with get_session() as session:
        async with session.begin():
            for rel_path, symbol_name, capability_name in TARGETS:
                path = Path(settings.REPO_PATH) / rel_path
                if not path.exists():
                    print(f"❌ File missing: {rel_path}")
                    continue

                content = path.read_text()
                lines = content.splitlines()
                found_uuid = None
                
                # Scan for ID
                for i, line in enumerate(lines):
                    # Match def or class
                    if f"def {symbol_name}" in line or f"class {symbol_name}" in line:
                        # Look backwards for ID
                        scan_idx = i - 1
                        while scan_idx >= 0:
                            if "# ID:" in lines[scan_idx]:
                                match = re.search(r"# ID: ([a-f0-9\-]+)", lines[scan_idx])
                                if match:
                                    found_uuid = match.group(1)
                                break
                            if lines[scan_idx].strip().startswith("def ") or lines[scan_idx].strip().startswith("class "):
                                break
                            scan_idx -= 1
                        if found_uuid: 
                            break
                
                if not found_uuid:
                    print(f"⚠️  No ID tag found for {symbol_name}")
                    continue

                # Register Capability (Ensure it exists)
                domain = capability_name.split('.')[0]
                await session.execute(text("""
                    INSERT INTO core.capabilities (name, domain, title, owner, status, tags)
                    VALUES (:name, :domain, :name, 'system', 'Active', '[]'::jsonb)
                    ON CONFLICT (domain, name) DO NOTHING
                """), {"name": capability_name, "domain": domain})

                # Get Capability ID
                res = await session.execute(text("SELECT id FROM core.capabilities WHERE name = :n"), {"n": capability_name})
                cap_id = res.scalar()

                if cap_id:
                    # Force the link
                    await session.execute(text("""
                        INSERT INTO core.symbol_capability_links 
                        (symbol_id, capability_id, confidence, source, verified)
                        VALUES (:sid, :cid, 1.0, 'manual', true)
                        ON CONFLICT (symbol_id, capability_id, source) DO NOTHING
                    """), {"sid": found_uuid, "cid": cap_id})
                    print(f"   ✅ RESTORED: {symbol_name} -> {capability_name}")
                else:
                    print(f"   ❌ Cap ID not found for {capability_name}")

    print("💾 Links restored.")

if __name__ == "__main__":
    asyncio.run(restore())