import asyncio
import json
from services.database.session_manager import get_session
from services.knowledge.knowledge_service import KnowledgeService

async def test_service():
    print("🕵️ Testing KnowledgeService Layer...")
    
    # Initialize the service
    service = KnowledgeService()
    
    # Fetch the graph
    print("   -> Calling get_graph()...")
    graph = await service.get_graph()
    symbols = graph.get("symbols", {})
    
    # Check the specific symbol 'feature' (located in src/body/cli/commands/develop.py)
    # We need to find the key that ends with ':feature'
    target = None
    for key, data in symbols.items():
        if key.endswith(":feature") and "develop.py" in key:
            target = data
            break
    
    if not target:
        print("❌ ERROR: Symbol 'feature' not found in KnowledgeService output.")
        print("   (The symbol discovery might be missing it entirely)")
        return

    print(f"✅ Found Symbol: {target.get('qualname', 'Unknown')}")
    
    # CRITICAL CHECK: Check the capability fields
    caps = target.get("capabilities")
    caps_array = target.get("capabilities_array")
    
    print(f"   • raw 'capabilities_array' from DB: {caps_array}")
    print(f"   • mapped 'capabilities' (Audit uses this): {caps}")
    
    if caps:
        print("✅ SUCCESS: The Service is mapping the capabilities correctly.")
        print("   If Audit still fails, the issue is in the Audit Check logic itself.")
    else:
        print("❌ FAILURE: 'capabilities' is EMPTY or None.")
        print("   -> The fix in src/services/knowledge/knowledge_service.py is MISSING or NOT WORKING.")
        print("   -> You need to re-apply the KnowledgeService fix.")

if __name__ == "__main__":
    asyncio.run(test_service())