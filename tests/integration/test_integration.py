"""Integration test for ContextService.

Tests full packet building pipeline without real DB/Qdrant.
"""

import asyncio
import logging
from pathlib import Path

from src.services.context.service import ContextService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_build_packet():
    """Test building a context packet."""
    logger.info("Starting ContextService integration test")

    # Initialize service (no DB/Qdrant)
    service = ContextService(project_root=".")

    # Create test task spec
    task_spec = {
        "task_id": "TEST_001",
        "task_type": "docstring.fix",
        "summary": "Test context packet building",
        "roots": ["src/"],
        "include": ["*.py"],
        "exclude": ["*test*", "*__pycache__*"],
        "max_tokens": 5000,
        "max_items": 5,
    }

    # Build packet
    logger.info("Building packet...")
    packet = await service.build_for_task(task_spec, use_cache=False)

    # Verify structure
    assert "header" in packet, "Missing header"
    assert "problem" in packet, "Missing problem"
    assert "scope" in packet, "Missing scope"
    assert "constraints" in packet, "Missing constraints"
    assert "context" in packet, "Missing context"
    assert "policy" in packet, "Missing policy"
    assert "provenance" in packet, "Missing provenance"

    # Verify header
    assert packet["header"]["packet_id"], "Missing packet_id"
    assert packet["header"]["task_id"] == "TEST_001", "Wrong task_id"
    assert packet["header"]["task_type"] == "docstring.fix", "Wrong task_type"
    assert packet["header"]["privacy"] == "local_only", "Wrong privacy"

    # Verify policy
    assert packet["policy"]["remote_allowed"] is False, "Should be local only"

    # Verify provenance
    assert packet["provenance"]["packet_hash"], "Missing packet_hash"
    assert packet["provenance"]["cache_key"], "Missing cache_key"
    assert "build_stats" in packet["provenance"], "Missing build_stats"

    # Verify file was created
    packet_path = Path("work/context_packets/TEST_001/context.yaml")
    assert packet_path.exists(), "Packet file not created"

    logger.info("✓ All assertions passed")
    logger.info(f"  Packet ID: {packet['header']['packet_id']}")
    logger.info(f"  Items: {len(packet['context'])}")
    logger.info(f"  Redactions: {len(packet['policy']['redactions_applied'])}")
    logger.info(
        f"  Build time: {packet['provenance']['build_stats'].get('duration_ms')}ms"
    )

    # Load and validate
    logger.info("Testing load...")
    loaded = await service.load_packet("TEST_001")
    assert loaded is not None, "Failed to load packet"
    assert loaded["header"]["packet_id"] == packet["header"]["packet_id"], (
        "Packet mismatch"
    )

    logger.info("✓ Load test passed")

    # Test validation
    is_valid, errors = service.validate_packet(packet)
    assert is_valid, f"Validation failed: {errors}"
    logger.info("✓ Validation test passed")

    logger.info("\n=== Integration test complete ===")
    return packet


if __name__ == "__main__":
    packet = asyncio.run(test_build_packet())
    print(f"\nPacket hash: {packet['provenance']['packet_hash'][:16]}...")
