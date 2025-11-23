import asyncio
from sqlalchemy import text
from services.database.session_manager import get_session

async def check_view():
    print("👀 inspecting core.knowledge_graph View for 'feature'...")
    
    async with get_session() as session:
        # Query the specific view the KnowledgeService uses
        result = await session.execute(text("""
            SELECT 
                name, 
                file_path, 
                capabilities_array, 
                status 
            FROM core.knowledge_graph 
            WHERE name = 'feature'
        """))
        
        row = result.fetchone()
        
        if not row:
            print("❌ Symbol 'feature' NOT FOUND in core.knowledge_graph view.")
            print("   -> The View logic might be filtering it out (e.g., status='deprecated'?)")
        else:
            print(f"✅ Found 'feature' in View.")
            print(f"   📂 File: {row.file_path}")
            print(f"   🧩 Capabilities Array: {row.capabilities_array}")
            
            if not row.capabilities_array or row.capabilities_array == []:
                print("   ❌ PROBLEM FOUND: The View sees the symbol, but 'capabilities_array' is EMPTY.")
                print("      -> This means the JOIN in the View definition isn't matching the Link Table.")
            else:
                print("   ✅ The View has the data!")
                print("   👉 CONCLUSION: The Database is perfect. The issue is your Python Pydantic Model.")
                print("      The Audit code is likely looking for a field that no longer matches this View.")

if __name__ == "__main__":
    asyncio.run(check_view())