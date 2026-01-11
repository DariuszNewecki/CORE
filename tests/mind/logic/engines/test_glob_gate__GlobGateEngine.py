"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/glob_gate.py
- Symbol: GlobGateEngine
- Status: 10 tests passed, some failed
- Passing tests: test_verify_no_violations, test_verify_exceptions, test_verify_max_lines_exceeded, test_verify_invalid_path, test_verify_multiple_parameter_names, test_verify_pattern_string_instead_of_list, test_match_basic_glob, test_verify_file_read_error, test_verify_thresholds_default_only, test_verify_empty_params
- Generated: 2026-01-11 02:17:16
"""

from pathlib import Path

import pytest

from mind.logic.engines.glob_gate import GlobGateEngine


@pytest.mark.asyncio
async def test_verify_no_violations():
    """Test basic case with no violations."""
    engine = GlobGateEngine()
    file_path = Path("some/file.py")
    params = {"patterns": ["*.txt"], "max_lines": 100}
    result = await engine.verify(file_path, params)
    assert result.ok
    assert result.message == "Path authorization verified."
    assert result.violations == []
    assert result.engine_id == "glob_gate"


@pytest.mark.asyncio
async def test_verify_exceptions():
    """Test exceptions override pattern matches."""
    engine = GlobGateEngine()
    file_path = Path("allowed/secret.txt")
    params = {"patterns": ["*.txt"], "exceptions": ["allowed/*"], "action": "block"}
    result = await engine.verify(file_path, params)
    assert result.ok
    assert result.violations == []


@pytest.mark.asyncio
async def test_verify_max_lines_exceeded():
    """Test max_lines violation."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        for i in range(5):
            f.write(f"Line {i}\n")
        temp_path = f.name
    try:
        engine = GlobGateEngine()
        params = {"max_lines": 3}
        result = await engine.verify(Path(temp_path), params)
        assert not result.ok
        assert len(result.violations) == 1
        assert "exceeds limit of 3" in result.violations[0]
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_verify_invalid_path():
    """Test handling of invalid path."""
    engine = GlobGateEngine()

    class InvalidPath:

        def __str__(self):
            raise ValueError("Invalid path encoding")

    invalid_path = InvalidPath()
    result = await engine.verify(invalid_path, {})
    assert not result.ok
    assert "Invalid path" in result.message
    assert result.violations == []
    assert result.engine_id == "glob_gate"


@pytest.mark.asyncio
async def test_verify_multiple_parameter_names():
    """Test different parameter names for patterns."""
    engine = GlobGateEngine()
    file_path = Path("forbidden/file.txt")
    params1 = {"patterns": ["*.txt"]}
    result1 = await engine.verify(file_path, params1)
    assert not result1.ok
    params2 = {"forbidden_paths": ["*.txt"]}
    result2 = await engine.verify(file_path, params2)
    assert not result2.ok
    params3 = {"patterns_prohibited": ["*.txt"]}
    result3 = await engine.verify(file_path, params3)
    assert not result3.ok


@pytest.mark.asyncio
async def test_verify_pattern_string_instead_of_list():
    """Test when patterns is a string instead of list."""
    engine = GlobGateEngine()
    file_path = Path("target/file.py")
    params = {"patterns": "*.py"}
    result = await engine.verify(file_path, params)
    assert not result.ok
    assert "matches restricted pattern" in result.violations[0]


@pytest.mark.asyncio
async def test_match_basic_glob():
    """Test _match method with basic glob patterns."""
    engine = GlobGateEngine()
    assert engine._match("src/file.py", "*.py")
    assert not engine._match("src/file.py", "*.js")
    assert engine._match("src/utils/file.py", "src/*")
    assert not engine._match("src/utils/file.py", "utils/*")


@pytest.mark.asyncio
async def test_verify_file_read_error():
    """Test that file read errors don't cause verify to fail."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("test\n")
        temp_path = f.name
    os.unlink(temp_path)
    engine = GlobGateEngine()
    params = {"max_lines": 10}
    result = await engine.verify(Path(temp_path), params)
    assert result.ok
    assert result.violations == []


@pytest.mark.asyncio
async def test_verify_thresholds_default_only():
    """Test thresholds with only default pattern."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        for i in range(15):
            f.write(f"Line {i}\n")
        temp_path = f.name
    try:
        engine = GlobGateEngine()
        params = {"thresholds": [{"path": "default", "limit": 10}]}
        result = await engine.verify(Path(temp_path), params)
        assert not result.ok
        assert "exceeds limit of 10" in result.violations[0]
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_verify_empty_params():
    """Test with empty parameters dict."""
    engine = GlobGateEngine()
    file_path = Path("any/file.py")
    result = await engine.verify(file_path, {})
    assert result.ok
    assert result.violations == []
