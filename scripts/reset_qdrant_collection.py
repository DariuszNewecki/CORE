#!/usr/bin/env python3
# scripts/reset_qdrant_collection.py
"""
Connects to Qdrant and completely resets the collection by deleting and recreating it.
"""
import asyncio
import os

from dotenv import load_dotenv
from qdrant_client import AsyncQdrantClient, models
from rich.console import Console

# Load environment variables from .env
load_dotenv()
console = Console()

# --- Configuration from .env ---
QDRANT_URL = os.getenv("QDRANT_URL")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")
VECTOR_DIMENSION = int(os.getenv("LOCAL_EMBEDDING_DIM", "768"))
# --- End Configuration ---


async def reset_collection():
    """Connects to Qdrant and idempotently recreates the collection."""
    if not all([QDRANT_URL, COLLECTION_NAME]):
        console.print("❌ Error: QDRANT_URL and QDRANT_COLLECTION_NAME must be set in your .env file.")
        return

    console.print(f"Connecting to Qdrant at {QDRANT_URL}...")
    client = AsyncQdrantClient(url=QDRANT_URL)

    try:
        console.print(f"Attempting to reset collection: '{COLLECTION_NAME}'...")
        # recreate_collection will delete if it exists, then create a new one.
        await client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        console.print(f"✅ Successfully reset collection '{COLLECTION_NAME}'.")

    except Exception as e:
        console.print(f"❌ An error occurred: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(reset_collection())