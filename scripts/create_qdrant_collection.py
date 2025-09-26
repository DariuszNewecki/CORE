import asyncio
from qdrant_client import AsyncQdrantClient, models

# --- Your Configuration ---
# These should match your .env file
QDRANT_URL = "http://192.168.20.22:6333"
COLLECTION_NAME = "core_capabilities"
VECTOR_DIMENSION = 768  # This must match your embedding model's output size
# --- End Configuration ---

async def create_collection():
    """
    Connects to Qdrant and idempotently creates the specified collection.
    """
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    client = AsyncQdrantClient(url=QDRANT_URL)

    try:
        # Check if the collection already exists
        collections_response = await client.get_collections()
        existing_collections = [c.name for c in collections_response.collections]
        
        if COLLECTION_NAME in existing_collections:
            print(f"✅ Collection '{COLLECTION_NAME}' already exists. Nothing to do.")
            return

        # If it doesn't exist, create it
        print(f"Collection '{COLLECTION_NAME}' not found. Creating it now...")
        await client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"✅ Successfully created collection '{COLLECTION_NAME}'.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("\nPlease ensure your Qdrant Docker container is running and accessible.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(create_collection())