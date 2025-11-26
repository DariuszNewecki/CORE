import asyncio
from pathlib import Path

from features.introspection.module_anchor_generator import ModuleAnchorGenerator
from services.clients.qdrant_client import QdrantService
from will.orchestration.cognitive_service import CognitiveService


async def test_placement():
    repo = Path("/opt/dev/CORE")
    q = QdrantService()
    c = CognitiveService(repo, q)
    await c.initialize()

    gen = ModuleAnchorGenerator(repo, c, q)

    # Test: Where should an email validator go?
    print("\n🎯 WHERE SHOULD THIS CODE GO?")
    print("=" * 60)
    print("Goal: Create an email validator that validates email format")
    print("      using regex and returns ValidationResult")
    print("=" * 60)

    results = await gen.find_best_placement(
        "Email validator class that validates email format using regex. "
        "Returns ValidationResult dataclass with is_valid and error_message.",
        limit=5,
    )

    print("\n📍 PLACEMENT OPTIONS:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['path']} (Score: {r['score']:.3f})")
        print(f"   Type: {r['type']}")
        print(f"   Layer: {r['layer']}")
        print(f"   Purpose: {r['purpose'][:80]}...")
        print()

    # Test: Where should a diff generator go?
    print("\n" + "=" * 60)
    print("Goal: Create a diff generator service that compares strings")
    print("=" * 60)

    results2 = await gen.find_best_placement(
        "Diff generation service that compares two strings and produces unified diff output",
        limit=5,
    )

    print("\n📍 PLACEMENT OPTIONS:\n")
    for i, r in enumerate(results2, 1):
        print(f"{i}. {r['path']} (Score: {r['score']:.3f})")
        print(f"   {r['purpose'][:60]}...")
        print()


asyncio.run(test_placement())
