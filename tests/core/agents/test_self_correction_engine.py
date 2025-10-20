from unittest.mock import AsyncMock, Mock, patch

import pytest
from core.agents.self_correction_engine import attempt_correction


@pytest.fixture
def mock_cognitive_service():
    """Fixture providing mock CognitiveService."""
    service = Mock()
    service.aget_client_for_role = AsyncMock()
    return service


@pytest.fixture
def mock_auditor_context():
    """Fixture providing mock AuditorContext."""
    context = Mock()
    return context


@pytest.fixture
def valid_failure_context():
    """Fixture providing valid failure context."""
    return {
        "file_path": "test_file.py",
        "code": "def test_function():\n    return 'test'",
        "violations": [{"type": "syntax_error", "message": "Missing colon", "line": 1}],
    }


@pytest.fixture
def mock_generator():
    """Fixture providing mock LLM generator."""
    generator = Mock()
    generator.make_request_async = AsyncMock()
    return generator


@pytest.mark.asyncio
async def test_attempt_correction_missing_context_fields(
    mock_cognitive_service, mock_auditor_context
):
    """Test attempt_correction returns error when required fields are missing."""
    # Arrange
    failure_context = {"file_path": "test.py"}  # Missing code and violations

    # Act
    result = await attempt_correction(
        failure_context, mock_cognitive_service, mock_auditor_context
    )

    # Assert
    assert result["status"] == "error"
    assert "Missing required failure context fields" in result["message"]


@pytest.mark.asyncio
@patch("core.agents.self_correction_engine.parse_write_blocks")
@patch("core.agents.self_correction_engine.PromptPipeline")
async def test_attempt_correction_success(
    mock_pipeline_class,
    mock_parse_write_blocks,
    mock_cognitive_service,
    mock_auditor_context,
    valid_failure_context,
    mock_generator,
):
    """Test successful code correction with validation."""
    # Arrange
    mock_cognitive_service.aget_client_for_role.return_value = mock_generator

    mock_pipeline = Mock()
    mock_pipeline.process.return_value = "processed_prompt"
    mock_pipeline_class.return_value = mock_pipeline

    mock_generator.make_request_async.return_value = (
        "[[write:test_file.py]]corrected_code[[/write]]"
    )

    mock_parse_write_blocks.return_value = {"test_file.py": "corrected_code_content"}

    with patch(
        "core.agents.self_correction_engine.validate_code_async"
    ) as mock_validate:
        mock_validate.return_value = {
            "status": "clean",
            "code": "validated_corrected_code",
            "violations": [],
        }

        # Act
        result = await attempt_correction(
            valid_failure_context, mock_cognitive_service, mock_auditor_context
        )

    # Assert
    assert result["status"] == "success"
    assert result["code"] == "validated_corrected_code"
    assert "Corrected code generated and validated successfully" in result["message"]

    mock_cognitive_service.aget_client_for_role.assert_awaited_once_with("Coder")
    mock_pipeline.process.assert_called_once()
    mock_generator.make_request_async.assert_awaited_once_with(
        "processed_prompt", user_id="auto_repair"
    )
    mock_parse_write_blocks.assert_called_once_with(
        "[[write:test_file.py]]corrected_code[[/write]]"
    )
    mock_validate.assert_awaited_once_with(
        "test_file.py", "corrected_code_content", mock_auditor_context
    )


@pytest.mark.asyncio
@patch("core.agents.self_correction_engine.parse_write_blocks")
@patch("core.agents.self_correction_engine.PromptPipeline")
async def test_attempt_correction_no_write_blocks(
    mock_pipeline_class,
    mock_parse_write_blocks,
    mock_cognitive_service,
    mock_auditor_context,
    valid_failure_context,
    mock_generator,
):
    """Test attempt_correction returns error when LLM doesn't produce write blocks."""
    # Arrange
    mock_cognitive_service.aget_client_for_role.return_value = mock_generator

    mock_pipeline = Mock()
    mock_pipeline.process.return_value = "processed_prompt"
    mock_pipeline_class.return_value = mock_pipeline

    mock_generator.make_request_async.return_value = "No write blocks in response"
    mock_parse_write_blocks.return_value = {}

    # Act
    result = await attempt_correction(
        valid_failure_context, mock_cognitive_service, mock_auditor_context
    )

    # Assert
    assert result["status"] == "error"
    assert (
        "LLM did not produce a valid correction in a write block" in result["message"]
    )

    mock_parse_write_blocks.assert_called_once_with("No write blocks in response")


@pytest.mark.asyncio
@patch("core.agents.self_correction_engine.parse_write_blocks")
@patch("core.agents.self_correction_engine.PromptPipeline")
async def test_attempt_correction_failed_validation(
    mock_pipeline_class,
    mock_parse_write_blocks,
    mock_cognitive_service,
    mock_auditor_context,
    valid_failure_context,
    mock_generator,
):
    """Test attempt_correction returns error when corrected code fails validation."""
    # Arrange
    mock_cognitive_service.aget_client_for_role.return_value = mock_generator

    mock_pipeline = Mock()
    mock_pipeline.process.return_value = "processed_prompt"
    mock_pipeline_class.return_value = mock_pipeline

    mock_generator.make_request_async.return_value = (
        "[[write:test_file.py]]corrected_code[[/write]]"
    )
    mock_parse_write_blocks.return_value = {"test_file.py": "corrected_code_content"}

    with patch(
        "core.agents.self_correction_engine.validate_code_async"
    ) as mock_validate:
        mock_validate.return_value = {
            "status": "dirty",
            "code": "invalid_corrected_code",
            "violations": [
                {"type": "new_error", "message": "Still has issues", "line": 2}
            ],
        }

        # Act
        result = await attempt_correction(
            valid_failure_context, mock_cognitive_service, mock_auditor_context
        )

    # Assert
    assert result["status"] == "correction_failed_validation"
    assert "The corrected code still fails validation" in result["message"]
    assert len(result["violations"]) == 1
    assert result["violations"][0]["type"] == "new_error"

    mock_validate.assert_awaited_once_with(
        "test_file.py", "corrected_code_content", mock_auditor_context
    )


@pytest.mark.asyncio
@patch("core.agents.self_correction_engine.PromptPipeline")
async def test_attempt_correction_prompt_generation(
    mock_pipeline_class,
    mock_cognitive_service,
    mock_auditor_context,
    valid_failure_context,
    mock_generator,
):
    """Test that the correction prompt is generated correctly."""
    # Arrange
    mock_cognitive_service.aget_client_for_role.return_value = mock_generator

    mock_pipeline = Mock()
    mock_pipeline.process.return_value = "final_processed_prompt"
    mock_pipeline_class.return_value = mock_pipeline

    with patch("core.agents.self_correction_engine.parse_write_blocks") as mock_parse:
        mock_parse.return_value = {"test_file.py": "corrected_code"}

        with patch(
            "core.agents.self_correction_engine.validate_code_async"
        ) as mock_validate:
            mock_validate.return_value = {"status": "clean", "code": "validated_code"}

            # Act
            await attempt_correction(
                valid_failure_context, mock_cognitive_service, mock_auditor_context
            )

    # Assert - Check that prompt processing was called
    mock_pipeline.process.assert_called_once()

    # Verify the prompt contains expected elements
    call_args = mock_pipeline.process.call_args[0][0]
    assert "self-correction agent" in call_args
    assert "test_file.py" in call_args
    assert "def test_function():" in call_args
    assert "violations" in call_args
    assert "syntax_error" in call_args
    assert "write:test_file.py" in call_args


@pytest.mark.asyncio
@patch("core.agents.self_correction_engine.settings")
@patch("core.agents.self_correction_engine.PromptPipeline")
async def test_attempt_correction_with_settings(
    mock_pipeline_class,
    mock_settings,
    mock_cognitive_service,
    mock_auditor_context,
    valid_failure_context,
    mock_generator,
):
    """Test that PromptPipeline is initialized with correct REPO_PATH from settings."""
    # Arrange
    mock_settings.REPO_PATH = "/test/repo/path"
    mock_cognitive_service.aget_client_for_role.return_value = mock_generator

    mock_pipeline = Mock()
    mock_pipeline.process.return_value = "processed_prompt"
    mock_pipeline_class.return_value = mock_pipeline

    with patch("core.agents.self_correction_engine.parse_write_blocks") as mock_parse:
        mock_parse.return_value = {"test_file.py": "corrected_code"}

        with patch(
            "core.agents.self_correction_engine.validate_code_async"
        ) as mock_validate:
            mock_validate.return_value = {"status": "clean", "code": "validated_code"}

            # Act
            await attempt_correction(
                valid_failure_context, mock_cognitive_service, mock_auditor_context
            )

    # Assert - Check that PromptPipeline was initialized with correct repo path
    mock_pipeline_class.assert_called_once_with(repo_path="/test/repo/path")


@pytest.mark.asyncio
@patch("core.agents.self_correction_engine.parse_write_blocks")
@patch("core.agents.self_correction_engine.PromptPipeline")
async def test_attempt_correction_multiple_write_blocks(
    mock_pipeline_class,
    mock_parse_write_blocks,
    mock_cognitive_service,
    mock_auditor_context,
    valid_failure_context,
    mock_generator,
):
    """Test that only the first write block is used when multiple are present."""
    # Arrange
    mock_cognitive_service.aget_client_for_role.return_value = mock_generator

    mock_pipeline = Mock()
    mock_pipeline.process.return_value = "processed_prompt"
    mock_pipeline_class.return_value = mock_pipeline

    mock_generator.make_request_async.return_value = "multiple write blocks response"

    # Return multiple write blocks but only first should be used
    mock_parse_write_blocks.return_value = {
        "test_file.py": "first_corrected_code",
        "another_file.py": "second_corrected_code",
    }

    with patch(
        "core.agents.self_correction_engine.validate_code_async"
    ) as mock_validate:
        mock_validate.return_value = {
            "status": "clean",
            "code": "validated_first_code",
            "violations": [],
        }

        # Act
        result = await attempt_correction(
            valid_failure_context, mock_cognitive_service, mock_auditor_context
        )

    # Assert - Only first write block should be validated
    assert result["status"] == "success"
    mock_validate.assert_awaited_once_with(
        "test_file.py", "first_corrected_code", mock_auditor_context
    )
