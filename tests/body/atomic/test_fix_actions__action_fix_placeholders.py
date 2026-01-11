"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/atomic/fix_actions.py
- Symbol: action_fix_placeholders
- Status: 9 tests passed, some failed
- Passing tests: test_action_fix_placeholders_no_changes_dry_run, test_action_fix_placeholders_with_changes_dry_run, test_action_fix_placeholders_with_changes_and_write, test_action_fix_placeholders_no_src_directory, test_action_fix_placeholders_empty_src_directory, test_action_fix_placeholders_error_handling, test_action_fix_placeholders_mixed_content, test_action_fix_placeholders_explicit_parameters, test_action_fix_placeholders_duration_measurement
- Generated: 2026-01-11 02:56:32
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from body.atomic.fix_actions import action_fix_placeholders


@pytest.mark.asyncio
async def test_action_fix_placeholders_no_changes_dry_run():
    """Test when no files need placeholder fixes (dry run)."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        test_file.write_text("print('Hello World')", encoding="utf-8")
        result = await action_fix_placeholders(mock_context, write=False)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["files_affected"] == 0
        assert result.data["written"] is False
        assert result.data["dry_run"] is True
        assert isinstance(result.duration_sec, float)
        assert result.duration_sec >= 0


@pytest.mark.asyncio
async def test_action_fix_placeholders_with_changes_dry_run():
    """Test when files need fixes but in dry run mode (write=False)."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        content = "# TODO: Implement this function…"
        test_file.write_text(content, encoding="utf-8")
        test_file2 = src_dir / "module" / "test2.py"
        test_file2.parent.mkdir()
        test_file2.write_text("# FIXME: This needs work…", encoding="utf-8")
        result = await action_fix_placeholders(mock_context, write=False)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["files_affected"] == 2
        assert result.data["written"] is False
        assert result.data["dry_run"] is True
        assert test_file.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_action_fix_placeholders_with_changes_and_write():
    """Test when files need fixes and write=True."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    mock_context.file_handler = Mock()
    mock_context.file_handler.write_runtime_text = Mock()
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        original_content = "# TODO: Fix this…"
        test_file.write_text(original_content, encoding="utf-8")
        result = await action_fix_placeholders(mock_context, write=True)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["files_affected"] == 1
        assert result.data["written"] is True
        assert result.data["dry_run"] is False
        mock_context.file_handler.write_runtime_text.assert_called_once()


@pytest.mark.asyncio
async def test_action_fix_placeholders_no_src_directory():
    """Test when src directory doesn't exist."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        result = await action_fix_placeholders(mock_context, write=False)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["files_affected"] == 0
        assert result.data["written"] is False


@pytest.mark.asyncio
async def test_action_fix_placeholders_empty_src_directory():
    """Test when src directory exists but has no Python files."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        (src_dir / "README.txt").write_text("Read me")
        (src_dir / "data.json").write_text("{}")
        result = await action_fix_placeholders(mock_context, write=False)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["files_affected"] == 0


@pytest.mark.asyncio
async def test_action_fix_placeholders_error_handling():
    """Test error handling when file reading fails."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        bad_file = src_dir / "bad.py"
        bad_file.mkdir()
        result = await action_fix_placeholders(mock_context, write=False)
        assert result.action_id == "fix.placeholders"
        assert result.ok is False
        assert "error" in result.data
        assert isinstance(result.data["error"], str)
        assert result.duration_sec >= 0


@pytest.mark.asyncio
async def test_action_fix_placeholders_mixed_content():
    """Test with mix of fixable and non-fixable content."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        file1 = src_dir / "file1.py"
        file1.write_text(
            "\ndef calculate():\n    # TODO: Implement calculation…\n    return None\n",
            encoding="utf-8",
        )
        file2 = src_dir / "file2.py"
        file2.write_text('\ndef hello():\n    return "Hello World"\n', encoding="utf-8")
        file3 = src_dir / "file3.py"
        file3.write_text(
            "\n# FIXME: This is broken…\nclass Broken:\n    pass\n", encoding="utf-8"
        )
        result = await action_fix_placeholders(mock_context, write=False)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["files_affected"] == 2
        assert result.data["written"] is False


@pytest.mark.asyncio
async def test_action_fix_placeholders_explicit_parameters():
    """Test with all parameters explicitly set."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        test_file.write_text("# TODO: Something…", encoding="utf-8")
        result = await action_fix_placeholders(core_context=mock_context, write=True)
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert result.data["written"] is True


@pytest.mark.asyncio
async def test_action_fix_placeholders_duration_measurement():
    """Verify duration is measured and returned."""
    mock_context = Mock()
    mock_git_service = Mock()
    mock_git_service.repo_path = Path("/fake/repo")
    mock_context.git_service = mock_git_service
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        mock_git_service.repo_path = repo_path
        src_dir = repo_path / "src"
        src_dir.mkdir()
        test_file = src_dir / "test.py"
        test_file.write_text("print('test')", encoding="utf-8")
        start_time = time.time()
        result = await action_fix_placeholders(mock_context, write=False)
        end_time = time.time()
        assert result.action_id == "fix.placeholders"
        assert result.ok is True
        assert isinstance(result.duration_sec, float)
        assert 0 <= result.duration_sec <= end_time - start_time + 1.0
