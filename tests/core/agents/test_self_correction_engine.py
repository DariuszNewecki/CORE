# tests/core/agents/test_self_correction_engine.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.agents.self_correction_engine import _attempt_correction


@pytest.fixture
def mock_pipeline(mocker):
    """Mocks the module-level pipeline instance used by the function under test."""
    mocked_pipeline = mocker.patch("will.agents.self_correction_engine.pipeline")
    mocked_pipeline.process.return_value = "Processed prompt"
    return mocked_pipeline


@pytest.fixture
def mock_cognitive_service():
    """Provides a mock CognitiveService with a mock LLM client."""
    mock_llm_client = MagicMock()
    mock_service = MagicMock()
    mock_service.aget_client_for_role = AsyncMock(return_value=mock_llm_client)
    return mock_service


@pytest.fixture
def mock_auditor_context():
    """Provides a mock AuditorContext."""
    return MagicMock()


@pytest.fixture
def mock_llm_client(mock_cognitive_service):
    """Get the mock LLM client from the cognitive service."""
    return mock_cognitive_service.aget_client_for_role.return_value


@pytest.mark.asyncio
async def test_attempt_correction_success(
    mock_pipeline, mock_cognitive_service, mock_auditor_context, mock_llm_client
):
    """Test successful correction with pipeline processing and LLM call."""
    # Mock the LLM response with a write block
    mock_llm_client.make_request_async = AsyncMock(
        return_value="[[write:test.py]]\nprint('hello')\n[[/write]]"
    )

    # Mock validate_code_async to return success
    with patch(
        "will.agents.self_correction_engine.validate_code_async"
    ) as mock_validate:
        mock_validate.return_value = {
            "status": "clean",
            "code": "print('hello')",
            "violations": [],
        }

        failure_context = {
            "file_path": "test.py",
            "code": "print('wrong')",
            "violations": ["syntax error"],
        }

        result = await _attempt_correction(
            failure_context=failure_context,
            cognitive_service=mock_cognitive_service,
            auditor_context=mock_auditor_context,
        )

    assert result["status"] == "success"
    assert result["code"] == "print('hello')"
    mock_llm_client.make_request_async.assert_called_once()
    mock_pipeline.process.assert_called_once()


@pytest.mark.asyncio
async def test_attempt_correction_missing_context(
    mock_cognitive_service, mock_auditor_context
):
    """Test error handling when failure_context is missing required fields."""
    failure_context = {
        "file_path": "test.py",
        # Missing 'code' and 'violations'
    }

    result = await _attempt_correction(
        failure_context=failure_context,
        cognitive_service=mock_cognitive_service,
        auditor_context=mock_auditor_context,
    )

    assert result["status"] == "error"
    assert "Missing required failure context" in result["message"]


@pytest.mark.asyncio
async def test_attempt_correction_llm_no_write_block(
    mock_pipeline, mock_cognitive_service, mock_auditor_context, mock_llm_client
):
    """Test error handling when LLM doesn't produce a write block."""
    mock_llm_client.make_request_async = AsyncMock(
        return_value="Some response without write blocks"
    )

    failure_context = {
        "file_path": "test.py",
        "code": "print('test')",
        "violations": ["error"],
    }

    result = await _attempt_correction(
        failure_context=failure_context,
        cognitive_service=mock_cognitive_service,
        auditor_context=mock_auditor_context,
    )

    assert result["status"] == "error"
    assert "LLM did not produce a valid correction" in result["message"]


@pytest.mark.asyncio
async def test_attempt_correction_validation_fails(
    mock_pipeline, mock_cognitive_service, mock_auditor_context, mock_llm_client
):
    """Test when corrected code still fails validation."""
    mock_llm_client.make_request_async = AsyncMock(
        return_value="[[write:test.py]]\nprint('fixed')\n[[/write]]"
    )

    with patch(
        "will.agents.self_correction_engine.validate_code_async"
    ) as mock_validate:
        mock_validate.return_value = {
            "status": "dirty",
            "code": "print('fixed')",
            "violations": ["still broken"],
        }

        failure_context = {
            "file_path": "test.py",
            "code": "print('broken')",
            "violations": ["error"],
        }

        result = await _attempt_correction(
            failure_context=failure_context,
            cognitive_service=mock_cognitive_service,
            auditor_context=mock_auditor_context,
        )

    assert result["status"] == "correction_failed_validation"
    assert "still broken" in result["violations"]


@pytest.mark.asyncio
async def test_attempt_correction_llm_error(
    mock_pipeline, mock_cognitive_service, mock_auditor_context, mock_llm_client
):
    """Test error handling when LLM call fails."""
    mock_llm_client.make_request_async = AsyncMock(side_effect=Exception("LLM error"))

    failure_context = {
        "file_path": "test.py",
        "code": "print('test')",
        "violations": ["error"],
    }

    result = await _attempt_correction(
        failure_context=failure_context,
        cognitive_service=mock_cognitive_service,
        auditor_context=mock_auditor_context,
    )

    assert result["status"] == "error"
