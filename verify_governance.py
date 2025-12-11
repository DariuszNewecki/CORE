import os
import sys
from pathlib import Path


sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    import asyncio

    from mind.governance.registry import GovernanceRegistry

    async def main():
        print("🔍 Scanning .intent/ for standardized policies...")
        registry = GovernanceRegistry(Path(".intent"))
        await registry.load()

        cs = registry.get_policy("code_standards")
        if cs:
            print(f"✅ Loaded Policy: {cs.metadata.title} (v{cs.metadata.version})")
            print(f"   - Found {len(cs.spec.rules)} rules")

            # Verify we kept the critical rules
            rule_ids = [r.id for r in cs.spec.rules]
            if "metadata.capability_id_required" in rule_ids:
                print("   - ✅ Capability IDs protected")
            else:
                print("   - ❌ MISSING: Capability IDs")

            if "metadata.cli_async_helpers_private" in rule_ids:
                print("   - ✅ CLI Async Shims protected")
            else:
                print("   - ❌ MISSING: CLI Async Shims")
        else:
            print("❌ Failed to load code_standards")

    if __name__ == "__main__":
        asyncio.run(main())

except ImportError as e:
    print(f"❌ Setup Error: {e}")
