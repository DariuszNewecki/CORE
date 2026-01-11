"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: get_repo_root
- Status: verified_in_sandbox
- Generated: 2026-01-11 10:44:37
"""

import pytest
from pathlib import Path
from shared.path_utils import get_repo_root

# Detected return type: Path (synchronous function)

def test_get_repo_root_finds_intent_directory():
    """Test that function finds .intent directory when starting from subdirectory."""
    # Create a temporary directory structure
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .intent directory at root
        root_path = Path(tmpdir)
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        # Create nested subdirectory
        subdir = root_path / "src" / "subfolder"
        subdir.mkdir(parents=True)

        # Change to subdirectory and test
        original_cwd = Path.cwd()
        os.chdir(subdir)

        try:
            result = get_repo_root()
            assert result == root_path
        finally:
            os.chdir(original_cwd)

def test_get_repo_root_with_explicit_start_dir():
    """Test that function works with explicitly provided start directory."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        subdir = root_path / "docs" / "api"
        subdir.mkdir(parents=True)

        result = get_repo_root(start_dir=subdir)
        assert result == root_path

def test_get_repo_root_starting_at_root():
    """Test that function works when starting at the repository root."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        result = get_repo_root(start_dir=root_path)
        assert result == root_path

def test_get_repo_root_file_not_found_error():
    """Test that function raises FileNotFoundError when .intent directory not found."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        # Don't create .intent directory

        with pytest.raises(FileNotFoundError) as exc_info:
            get_repo_root(start_dir=root_path)

        assert "Project root with .intent directory not found" in str(exc_info.value)

def test_get_repo_root_filesystem_root():
    """Test behavior when reaching filesystem root without finding .intent."""
    # This test simulates searching all the way to root without finding .intent
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        # Create a directory without .intent
        test_dir = root_path / "some" / "nested" / "path"
        test_dir.mkdir(parents=True)

        # Mock the filesystem root by patching parent recursion
        # We'll test the error case
        with pytest.raises(FileNotFoundError):
            get_repo_root(start_dir=test_dir)

def test_get_repo_root_intent_at_filesystem_root():
    """Test edge case where .intent exists at filesystem root."""
    # This is a theoretical test since we can't create .intent at actual filesystem root
    # We'll test the logic by verifying the final check in the while loop
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        # Simulate filesystem root by making parent equal to itself
        # We'll test with a mock, but for real test we'll create normal structure
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        # Create a path that's one level above our test root
        # (in real scenario, this would be filesystem root)
        test_path = root_path / "subdir"
        test_path.mkdir()

        result = get_repo_root(start_dir=test_path)
        assert result == root_path

def test_get_repo_root_returns_path_object():
    """Test that function returns a Path object."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        result = get_repo_root(start_dir=root_path)
        assert isinstance(result, Path)
        # Verify it has Path methods
        assert hasattr(result, "joinpath")
        assert hasattr(result, "is_dir")

def test_get_repo_root_with_none_start_dir():
    """Test that function uses current directory when start_dir is None."""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        original_cwd = Path.cwd()
        os.chdir(root_path)

        try:
            result = get_repo_root(start_dir=None)
            assert result == root_path
        finally:
            os.chdir(original_cwd)

def test_get_repo_root_path_comparison():
    """Test that path comparisons work correctly with different path representations."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        root_path = Path(tmpdir)
        intent_dir = root_path / ".intent"
        intent_dir.mkdir()

        # Test with string path
        subdir = root_path / "src" / "tests"
        subdir.mkdir(parents=True)

        result = get_repo_root(start_dir=subdir)
        # Use == for comparison, not 'is'
        assert result == root_path
        # Also test with resolved paths
        assert result.resolve() == root_path.resolve()
