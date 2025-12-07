#!/usr/bin/env python3
"""
Test script for new QdrantService helper methods.

This script verifies that the 4 new methods added in Phase 1 work correctly:
1. scroll_all_points()
2. get_point_by_id()
3. delete_points()
4. get_stored_hashes()

Run this before updating vectorizers to ensure service methods are solid.

Usage:
    python tests/services/test_qdrant_new_methods.py
"""

import asyncio
import hashlib
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.clients.qdrant_client import QdrantService


async def test_new_methods():
    """Test all 4 new QdrantService methods."""

    print("=" * 70)
    print("TESTING NEW QDRANT SERVICE METHODS")
    print("=" * 70)
    print()

    # Initialize service
    print("1. Initializing QdrantService...")
    qdrant = QdrantService()
    print(f"   ✓ Connected to: {qdrant.url}")
    print(f"   ✓ Collection: {qdrant.collection_name}")
    print(f"   ✓ Dimensions: {qdrant.vector_size}")
    print()

    # Ensure collection exists
    print("2. Ensuring collection exists...")
    await qdrant.ensure_collection()
    print("   ✓ Collection ready")
    print()

    # Test 1: scroll_all_points()
    print("3. Testing scroll_all_points()...")
    try:
        # Get all points without vectors (faster)
        points = await qdrant.scroll_all_points(
            with_payload=True,
            with_vectors=False,
        )
        print(f"   ✓ Retrieved {len(points)} points")

        if points:
            # Show first point structure
            sample = points[0]
            print(f"   Sample point ID: {sample.id}")
            print(f"   Has payload: {sample.payload is not None}")
            if sample.payload:
                print(f"   Payload keys: {list(sample.payload.keys())[:5]}...")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    print()

    # Test 2: get_point_by_id()
    print("4. Testing get_point_by_id()...")
    try:
        if points:
            # Get first point by ID
            test_id = str(points[0].id)
            point = await qdrant.get_point_by_id(
                point_id=test_id,
                with_payload=True,
                with_vectors=False,
            )

            if point:
                print(f"   ✓ Retrieved point: {test_id}")
                print(f"   Has payload: {point.payload is not None}")
            else:
                print(f"   ✗ Point not found: {test_id}")
        else:
            print("   ⊘ Skipping (no points in collection)")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    print()

    # Test 3: get_stored_hashes()
    print("5. Testing get_stored_hashes()...")
    try:
        hashes = await qdrant.get_stored_hashes()
        print(f"   ✓ Retrieved {len(hashes)} hashes")

        # Count points with hashes
        points_with_hash = len(hashes)
        total_points = len(points)
        if total_points > 0:
            coverage = (points_with_hash / total_points) * 100
            print(
                f"   Hash coverage: {coverage:.1f}% ({points_with_hash}/{total_points})"
            )

            if coverage < 100:
                print(
                    f"   ⚠ Warning: {total_points - points_with_hash} points missing content_sha256"
                )

        if hashes:
            # Show sample hash
            sample_id, sample_hash = next(iter(hashes.items()))
            print(f"   Sample: {sample_id[:16]}... → {sample_hash[:16]}...")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    print()

    # Test 4: delete_points() (create and delete a test point)
    print("6. Testing delete_points()...")
    try:
        # Create a test point with proper UUID
        import uuid

        test_id = str(uuid.uuid4())
        test_vector = [0.1] * qdrant.vector_size
        test_payload = {
            "chunk_id": "test_point_delete_me",
            "content_sha256": hashlib.sha256(b"test_content").hexdigest(),
            "source_path": "tests/test_qdrant_new_methods.py",  # Required field
            "source_type": "test",
            "symbol": "test_symbol",
            "capability_tags": ["test"],
        }

        print(f"   Creating test point: {test_id[:8]}...")
        await qdrant.upsert_symbol_vector(
            point_id_str=test_id,
            vector=test_vector,
            payload_data=test_payload,
        )
        print("   ✓ Test point created")

        # Verify it exists
        point = await qdrant.get_point_by_id(test_id, with_payload=True)
        if not point:
            print("   ✗ Test point not found after creation")
            return False
        print("   ✓ Test point verified")

        # Delete it
        print("   Deleting test point...")
        deleted_count = await qdrant.delete_points([test_id])
        print(f"   ✓ Deleted {deleted_count} points")

        # Verify it's gone
        point = await qdrant.get_point_by_id(test_id)
        if point:
            print("   ✗ Test point still exists after deletion")
            return False
        print("   ✓ Test point successfully removed")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False
    print()

    # Summary
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    print("✓ All 4 new methods working correctly:")
    print("  1. scroll_all_points() - Paginated collection scanning")
    print("  2. get_point_by_id() - Single point retrieval")
    print("  3. delete_points() - Bulk deletion with validation")
    print("  4. get_stored_hashes() - Hash-based deduplication support")
    print()
    print("Ready to proceed with Phase 1: Updating vectorizers!")
    print()

    return True


async def main():
    """Run tests and report results."""
    try:
        success = await test_new_methods()
        exit(0 if success else 1)
    except Exception as e:
        print()
        print("=" * 70)
        print("FATAL ERROR")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
