"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/sync_actions.py
- Symbol: action_sync_constitutional_vectors
- Status: 4 tests passed, some failed
- Passing tests: test_action_sync_constitutional_vectors_dry_run, test_action_sync_constitutional_vectors_no_cognitive_service, test_action_sync_constitutional_vectors_embedding_service_unavailable, test_action_sync_constitutional_vectors_exception_handling
- Generated: 2026-01-11 03:04:52
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from body.atomic.sync_actions import action_sync_constitutional_vectors


@pytest.mark.asyncio
async def test_action_sync_constitutional_vectors_dry_run():
    """Test dry-run mode returns skipped ActionResult."""
    mock_context = Mock()
    result = await action_sync_constitutional_vectors(mock_context, write=False)
    assert result.action_id == "sync.vectors.constitution"
    assert result.ok
    assert result.data["dry_run"]
    assert result.data["status"] == "skipped"
    assert isinstance(result.duration_sec, float)
    assert result.duration_sec >= 0


@pytest.mark.asyncio
async def test_action_sync_constitutional_vectors_no_cognitive_service():
    """Test when cognitive service is unavailable."""
    mock_context = Mock()
    mock_context.cognitive_service = None
    mock_context.registry = Mock()
    mock_context.registry.get_cognitive_service = AsyncMock(return_value=None)
    result = await action_sync_constitutional_vectors(mock_context, write=True)
    assert result.action_id == "sync.vectors.constitution"
    assert result.ok
    assert result.data["status"] == "skipped"
    assert result.data["reason"] == "cognitive_service_unavailable"
    assert isinstance(result.duration_sec, float)


@pytest.mark.asyncio
async def test_action_sync_constitutional_vectors_embedding_service_unavailable():
    """Test when embedding service test fails."""
    mock_context = Mock()
    mock_cognitive = AsyncMock()
    mock_cognitive.get_embedding_for_code = AsyncMock(return_value=None)
    mock_context.cognitive_service = mock_cognitive
    result = await action_sync_constitutional_vectors(mock_context, write=True)
    assert result.action_id == "sync.vectors.constitution"
    assert result.ok
    assert result.data["status"] == "skipped"
    assert result.data["reason"] == "embedding_service_unavailable"
    assert isinstance(result.duration_sec, float)


@pytest.mark.asyncio
async def test_action_sync_constitutional_vectors_exception_handling():
    """Test exception handling when vectorization fails."""
    mock_context = Mock()
    mock_cognitive = AsyncMock()
    mock_cognitive.get_embedding_for_code = AsyncMock(return_value=[0.1, 0.2, 0.3])
    mock_context.cognitive_service = mock_cognitive
    mock_adapter = Mock()
    mock_adapter.policies_to_items = Mock(side_effect=RuntimeError("Test error"))
    with patch(
        "body.atomic.sync_actions.ConstitutionalAdapter", return_value=mock_adapter
    ):
        result = await action_sync_constitutional_vectors(mock_context, write=True)
    assert result.action_id == "sync.vectors.constitution"
    assert not result.ok
    assert "error" in result.data
    assert "Test error" in result.data["error"]
    assert isinstance(result.duration_sec, float)
    assert result.duration_sec >= 0
