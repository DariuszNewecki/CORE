"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/atomic/sync_actions.py
- Symbol: action_sync_code_vectors
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:03:48
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from body.atomic.sync_actions import action_sync_code_vectors

# Detected return type: ActionResult (from the function signature)

@pytest.mark.asyncio
async def test_action_sync_code_vectors_success_dry_run():
    """Test successful execution in dry-run mode (write=False)."""
    mock_context = MagicMock()

    with patch('body.atomic.sync_actions.get_session') as mock_get_session, \
         patch('body.atomic.sync_actions.run_vectorize') as mock_run_vectorize:

        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        result = await action_sync_code_vectors(
            core_context=mock_context,
            write=False,
            force=False
        )

        mock_run_vectorize.assert_called_once_with(
            context=mock_context,
            session=mock_session,
            dry_run=True,  # not write = True
            force=False
        )

        assert result.action_id == "sync.vectors.code"
        assert result.ok is True
        assert result.data["status"] == "completed"
        assert result.data["dry_run"] is True
        assert result.data["force"] is False
        assert isinstance(result.duration_sec, float)
        assert result.duration_sec >= 0

@pytest.mark.asyncio
async def test_action_sync_code_vectors_success_write_mode():
    """Test successful execution with write=True."""
    mock_context = MagicMock()

    with patch('body.atomic.sync_actions.get_session') as mock_get_session, \
         patch('body.atomic.sync_actions.run_vectorize') as mock_run_vectorize:

        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        result = await action_sync_code_vectors(
            core_context=mock_context,
            write=True,
            force=False
        )

        mock_run_vectorize.assert_called_once_with(
            context=mock_context,
            session=mock_session,
            dry_run=False,  # not write = False
            force=False
        )

        assert result.action_id == "sync.vectors.code"
        assert result.ok is True
        assert result.data["status"] == "completed"
        assert result.data["dry_run"] is False
        assert result.data["force"] is False

@pytest.mark.asyncio
async def test_action_sync_code_vectors_success_force_mode():
    """Test successful execution with force=True."""
    mock_context = MagicMock()

    with patch('body.atomic.sync_actions.get_session') as mock_get_session, \
         patch('body.atomic.sync_actions.run_vectorize') as mock_run_vectorize:

        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        result = await action_sync_code_vectors(
            core_context=mock_context,
            write=False,
            force=True
        )

        mock_run_vectorize.assert_called_once_with(
            context=mock_context,
            session=mock_session,
            dry_run=True,
            force=True
        )

        assert result.action_id == "sync.vectors.code"
        assert result.ok is True
        assert result.data["status"] == "completed"
        assert result.data["dry_run"] is True
        assert result.data["force"] is True

@pytest.mark.asyncio
async def test_action_sync_code_vectors_exception_handling():
    """Test exception handling when run_vectorize raises an error."""
    mock_context = MagicMock()

    with patch('body.atomic.sync_actions.get_session') as mock_get_session, \
         patch('body.atomic.sync_actions.run_vectorize') as mock_run_vectorize, \
         patch('body.atomic.sync_actions.logger') as mock_logger:

        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        test_error = ValueError("Test error message")
        mock_run_vectorize.side_effect = test_error

        result = await action_sync_code_vectors(
            core_context=mock_context,
            write=False,
            force=False
        )

        mock_logger.error.assert_called_once()
        assert "Code vectorization failed" in mock_logger.error.call_args[0][0]

        assert result.action_id == "sync.vectors.code"
        assert result.ok is False
        assert result.data["error"] == "Test error message"
        assert isinstance(result.duration_sec, float)
        assert result.duration_sec >= 0

@pytest.mark.asyncio
async def test_action_sync_code_vectors_default_parameters():
    """Test with default parameters (write=False, force=False)."""
    mock_context = MagicMock()

    with patch('body.atomic.sync_actions.get_session') as mock_get_session, \
         patch('body.atomic.sync_actions.run_vectorize') as mock_run_vectorize:

        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        result = await action_sync_code_vectors(core_context=mock_context)

        mock_run_vectorize.assert_called_once_with(
            context=mock_context,
            session=mock_session,
            dry_run=True,  # default write=False
            force=False    # default force=False
        )

        assert result.ok is True
        assert result.data["dry_run"] is True
        assert result.data["force"] is False

@pytest.mark.asyncio
async def test_action_sync_code_vectors_duration_measurement():
    """Test that duration is properly measured."""
    mock_context = MagicMock()

    with patch('body.atomic.sync_actions.get_session') as mock_get_session, \
         patch('body.atomic.sync_actions.run_vectorize') as mock_run_vectorize, \
         patch('body.atomic.sync_actions.time') as mock_time:

        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__.return_value = mock_session

        mock_time.time.side_effect = [100.0, 102.5]  # start, end

        result = await action_sync_code_vectors(
            core_context=mock_context,
            write=False,
            force=False
        )

        assert result.duration_sec == 2.5
        assert mock_time.time.call_count == 2
