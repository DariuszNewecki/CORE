"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/llm_gate.py
- Symbol: LLMGateEngine
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:22:45
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from mind.logic.engines.llm_gate import LLMGateEngine


# TARGET CODE ANALYSIS:
# - verify() is async (starts with 'async def')
# - Returns EngineResult objects
# - Uses caching based on instruction+content hash
# - Handles file I/O errors
# - Handles LLM response parsing errors


@pytest.mark.asyncio
async def test_verify_successful_no_violation():
    """Test successful verification with no violation."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {"violation": False, "reasoning": "Code follows the rule", "finding": None}
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    params = {
        "instruction": "Functions must have docstrings",
        "rationale": "Documentation is important",
    }

    # Execute
    result = await engine.verify(file_path, params)

    # Assert
    assert result.ok
    assert result.message == "Semantic adherence verified."
    assert result.violations == []
    assert result.engine_id == "llm_gate"

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_successful_with_violation():
    """Test successful verification with violation."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {
            "violation": True,
            "reasoning": "Function lacks docstring",
            "finding": "Missing documentation",
        }
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    params = {
        "instruction": "Functions must have docstrings",
        "rationale": "Documentation is important",
    }

    # Execute
    result = await engine.verify(file_path, params)

    # Assert
    assert not result.ok
    assert result.message == "Semantic Violation: Function lacks docstring"
    assert result.violations == ["Missing documentation"]
    assert result.engine_id == "llm_gate"

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_with_violation_no_finding():
    """Test verification with violation but no finding string."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {"violation": True, "reasoning": "Function lacks docstring", "finding": None}
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    params = {
        "instruction": "Functions must have docstrings",
        "rationale": "Documentation is important",
    }

    # Execute
    result = await engine.verify(file_path, params)

    # Assert
    assert not result.ok
    assert result.message == "Semantic Violation: Function lacks docstring"
    assert result.violations == []
    assert result.engine_id == "llm_gate"

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_file_read_error():
    """Test handling of file read errors."""
    # Setup
    mock_llm = AsyncMock()
    engine = LLMGateEngine(llm_client=mock_llm)

    # Non-existent file
    file_path = Path("/non/existent/file.py")
    params = {"instruction": "Test rule", "rationale": "Test rationale"}

    # Execute
    result = await engine.verify(file_path, params)

    # Assert
    assert not result.ok
    assert "IO Error" in result.message
    assert result.violations == []
    assert result.engine_id == "llm_gate"
    mock_llm.make_request.assert_not_called()


@pytest.mark.asyncio
async def test_verify_llm_request_error():
    """Test handling of LLM request errors."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.side_effect = Exception("API timeout")

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    params = {"instruction": "Test rule", "rationale": "Test rationale"}

    # Execute
    result = await engine.verify(file_path, params)

    # Assert
    assert not result.ok
    assert "LLM Reasoning Failed" in result.message
    assert result.violations == []
    assert result.engine_id == "llm_gate"

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_invalid_json_response():
    """Test handling of invalid JSON response from LLM."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = "Not valid JSON"

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    params = {"instruction": "Test rule", "rationale": "Test rationale"}

    # Execute
    result = await engine.verify(file_path, params)

    # Assert
    assert not result.ok
    assert "LLM Reasoning Failed" in result.message
    assert result.violations == []
    assert result.engine_id == "llm_gate"

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_cache_hit():
    """Test that identical requests use cache."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {"violation": False, "reasoning": "Cached result", "finding": None}
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    content = "def foo(): pass"
    file_path.write_text(content, encoding="utf-8")

    params = {"instruction": "Cache test rule", "rationale": "Cache test rationale"}

    # First call - should call LLM
    result1 = await engine.verify(file_path, params)
    assert mock_llm.make_request.call_count == 1

    # Second call with same content - should use cache
    result2 = await engine.verify(file_path, params)
    assert mock_llm.make_request.call_count == 1  # No additional call

    # Results should be the same object (cached)
    assert result1 is result2

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_cache_miss_different_content():
    """Test cache miss when content changes."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {"violation": False, "reasoning": "Test result", "finding": None}
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")

    # First call
    file_path.write_text("content1", encoding="utf-8")
    params = {"instruction": "rule", "rationale": "rationale"}
    await engine.verify(file_path, params)

    # Second call with different content
    file_path.write_text("content2", encoding="utf-8")
    await engine.verify(file_path, params)

    # Should call LLM twice
    assert mock_llm.make_request.call_count == 2

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_cache_miss_different_instruction():
    """Test cache miss when instruction changes."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {"violation": False, "reasoning": "Test result", "finding": None}
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    # First call
    params1 = {"instruction": "rule1", "rationale": "rationale"}
    await engine.verify(file_path, params1)

    # Second call with different instruction
    params2 = {"instruction": "rule2", "rationale": "rationale"}
    await engine.verify(file_path, params2)

    # Should call LLM twice
    assert mock_llm.make_request.call_count == 2

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_default_rationale():
    """Test that default rationale is used when not provided."""
    # Setup
    mock_llm = AsyncMock()
    mock_llm.make_request.return_value = json.dumps(
        {"violation": False, "reasoning": "Test", "finding": None}
    )

    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    # No rationale in params
    params = {"instruction": "Test rule"}

    # Execute
    result = await engine.verify(file_path, params)

    # Assert - should work with default rationale
    assert result.ok

    # Cleanup
    file_path.unlink()


@pytest.mark.asyncio
async def test_verify_missing_instruction():
    """Test behavior when instruction is missing from params."""
    # Setup
    mock_llm = AsyncMock()
    engine = LLMGateEngine(llm_client=mock_llm)
    file_path = Path("/tmp/test.py")
    file_path.write_text("def foo(): pass", encoding="utf-8")

    # Empty params dict
    params = {}

    # Execute
    result = await engine.verify(file_path, params)

    # Assert - should still proceed (instruction will be None)
    # The LLM will receive "RULE TO ENFORCE: None"
    assert mock_llm.make_request.called

    # Cleanup
    file_path.unlink()


def test_engine_id():
    """Test that engine_id is correctly set."""
    engine = LLMGateEngine(llm_client=Mock())
    assert engine.engine_id == "llm_gate"


def test_init_with_custom_llm_client():
    """Test initialization with custom LLM client."""
    mock_llm = Mock()
    engine = LLMGateEngine(llm_client=mock_llm)
    assert engine.llm is mock_llm


def test_init_without_llm_client():
    """Test initialization without LLM client (should create default)."""
    # This tests that the engine can be initialized without a client
    # The actual LLMClient creation depends on settings, which we don't mock
    # So we just verify the engine can be instantiated
    engine = LLMGateEngine(llm_client=None)
    assert hasattr(engine, "llm")
    assert hasattr(engine, "_cache")
    assert isinstance(engine._cache, dict)
