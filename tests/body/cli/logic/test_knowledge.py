# tests/body/cli/logic/test_knowledge.py

from __future__ import annotations

from unittest.mock import patch

import pytest


try:
    from body.cli.logic.knowledge import find_common_knowledge

    _KNOWLEDGE_AVAILABLE = True
except ImportError:  # pragma: no cover
    find_common_knowledge = None
    _KNOWLEDGE_AVAILABLE = False


@pytest.mark.skipif(not _KNOWLEDGE_AVAILABLE, reason="knowledge module not available")
@pytest.mark.asyncio
async def test_find_common_knowledge():
    """Test that find_common_knowledge runs async workflow and returns clusters."""
    if not _KNOWLEDGE_AVAILABLE:
        pytest.skip("knowledge module not available")

    mock_result = {"hash1": [("file1.py", 10), ("file2.py", 20)]}
    with patch(
        "body.cli.logic.knowledge.asyncio.to_thread", return_value=mock_result
    ) as mocked_to_thread:
        result = await find_common_knowledge(min_occurrences=3, max_lines=10)

    mocked_to_thread.assert_called_once()
    assert result
    assert "cluster_1" in result
