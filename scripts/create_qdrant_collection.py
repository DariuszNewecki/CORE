# scripts/create_qdrant_collection.py
"""
Connects to Qdrant and idempotently creates the vector collection
using configuration from the project's .env file.
"""
import asyncio
import os

from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient, models

# Load environment variables from the .env file in the project root
load_dotenv()

# --- Configuration from .env ---
# These variables MUST be in your .env file for this script to work.
QDRANT_URL = os.getenv("QDRANT_URL")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")
VECTOR_DIMENSION_STR = os.getenv("LOCAL_EMBEDDING_DIM")
# --- End Configuration ---


async def create_collection():
    """
    Connects to Qdrant and idempotently creates the specified collection.
    """
    # --- Input Validation ---
    if not all([QDRANT_URL, COLLECTION_NAME, VECTOR_DIMENSION_STR]):
        print("❌ Error: QDRANT_URL, QDRANT_COLLECTION_NAME, and LOCAL_EMBEDDING_DIM must be set in your .env file.")
        return

    try:
        vector_dimension = int(VECTOR_DIMENSION_STR)
    except (ValueError, TypeError):
        print(f"❌ Error: Invalid LOCAL_EMBEDDING_DIM '{VECTOR_DIMENSION_STR}'. Must be an integer.")
        return
    # --- End Validation ---

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
                size=vector_dimension,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"✅ Successfully created collection '{COLLECTION_NAME}'.")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("\nPlease ensure your Qdrant Docker container is running and accessible at the URL specified in your .env file.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(create_collection())