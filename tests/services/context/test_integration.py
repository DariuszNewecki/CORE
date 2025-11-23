# tests/services/context/test_integration.py
"""
Integration test for ContextPackage end-to-end flow.
Tests building a context packet for a real function from the codebase.
"""

from pathlib import Path

import pytest

from services.clients.qdrant_client import QdrantService
from services.context.builder import ContextBuilder
from services.context.providers.ast import ASTProvider
from services.context.providers.db import DBProvider
from services.context.providers.vectors import VectorProvider
from services.context.serializers import ContextSerializer
from services.context.validator import ContextValidator
from services.database.session_manager import get_session
from shared.config import settings


@pytest.mark.asyncio
async def test_build_context_for_display_success():
    """
    Test building a complete context packet for display_success function.

    This validates:
    - Builder can orchestrate all providers
    - AST provider extracts function code
    - Packet validates against schema
    - Contains expected information
    """
    # Arrange: Create task specification
    task_spec = {
        "task_id": "TEST_001",
        "task_type": "test_generation",
        "target_symbol": "display_success",
        "target_file": "src/shared/cli_utils.py",
        "scope": {
            "include": ["src/shared/*.py"],
            "exclude": [],
            "roots": ["src/shared"],
        },
        "constraints": {
            "max_tokens": 2000,
            "max_items": 10,
        },
    }

    # Act: Build context packet
    async with get_session() as db:
        # Initialize providers with correct parameters
        ast_provider = ASTProvider(project_root=str(settings.REPO_PATH))
        db_provider = DBProvider()
        vector_provider = VectorProvider(qdrant_client=QdrantService())

        # Builder config
        config = {
            "max_tokens": 8000,
            "max_context_items": 50,
        }

        builder = ContextBuilder(
            db_provider=db_provider,
            vector_provider=vector_provider,
            ast_provider=ast_provider,
            config=config,
        )

        packet = await builder.build_for_task(task_spec)

    # Assert: Validate packet structure
    validator = ContextValidator()
    is_valid, errors = validator.validate(packet)

    assert is_valid, f"Packet validation failed: {errors}"

    # Assert: Check packet contents
    assert packet["header"]["task_id"] == "TEST_001"
    assert packet["header"]["task_type"] == "test_generation"

    # DEBUG: Print packet structure
    context_items = packet.get("context", [])
    print("\n=== DEBUG: Packet structure ===")
    print(f"Packet keys: {list(packet.keys())}")
    print(f"Header: {packet.get('header')}")
    print(f"Context items count: {len(context_items)}")
    if len(context_items) > 0:
        print(f"First context item: {context_items[0]}")
    else:
        print("Context is EMPTY!")
        print(f"Full packet: {packet}")

    # Assert: Context should contain the function code
    assert len(context_items) > 0, "Context should not be empty"

    # Assert: Should have at least the target function
    function_items = [
        item
        for item in context_items
        if item.get("item_type") == "code"
        and "display_success" in item.get("content", "")
    ]
    assert len(function_items) > 0, "Should contain display_success function code"

    # Assert: Packet should be serializable
    serializer = ContextSerializer()
    output_path = Path("/tmp/test_context_packet.yaml")
    serializer.to_yaml(packet, str(output_path))

    # Verify we can read it back
    loaded_packet = serializer.from_yaml(str(output_path))
    assert loaded_packet["header"]["task_id"] == "TEST_001"

    # Cleanup
    output_path.unlink(missing_ok=True)
