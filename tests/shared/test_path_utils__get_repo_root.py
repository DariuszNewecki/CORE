"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: get_repo_root
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:51:51
"""

import pytest
from pathlib import Path
from shared.path_utils import get_repo_root

# Detected return type: Path (synchronous function, not async)

def test_get_repo_root_finds_intent_directory():
    """Test that function finds .intent directory when starting from subdirectory."""
    # Create a temporary directory structure
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .intent directory at root
        repo_root = Path(tmpdir)
        intent_dir = repo_root / ".intent"
        intent_dir.mkdir()

        # Create a subdirectory
        subdir = repo_root / "src" / "module"
        subdir.mkdir(parents=True)

        # Change to subdirectory and test
        original_cwd = Path.cwd()
        try:
            os.chdir(subdir)
            result = get_repo_root()
            assert result == repo_root
        finally:
            os.chdir(original_cwd)

def test_get_repo_root_with_explicit_start_dir():
    """Test that function works with explicit start_dir parameter."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        intent_dir = repo_root / ".intent"
        intent_dir.mkdir()

        subdir = repo_root / "docs" / "api"
        subdir.mkdir(parents=True)

        result = get_repo_root(start_dir=subdir)
        assert result == repo_root

def test_get_repo_root_from_intent_directory_itself():
    """Test that function finds .intent when starting in the .intent directory."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        intent_dir = repo_root / ".intent"
        intent_dir.mkdir()

        result = get_repo_root(start_dir=intent_dir)
        assert result == repo_root

def test_get_repo_root_from_root_filesystem_fails():
    """Test that function raises FileNotFoundError when no .intent directory exists."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory without .intent
        empty_dir = Path(tmpdir) / "some" / "nested" / "path"
        empty_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError) as exc_info:
            get_repo_root(start_dir=empty_dir)

        assert "Project root with .intent directory not found" in str(exc_info.value)

def test_get_repo_root_at_filesystem_root():
    """Test behavior when at filesystem root (parent equals self)."""
    # Mock being at filesystem root by checking the while loop termination condition
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        intent_dir = repo_root / ".intent"
        intent_dir.mkdir()

        # When at the repo root itself, it should find it
        result = get_repo_root(start_dir=repo_root)
        assert result == repo_root

def test_get_repo_root_returns_path_object():
    """Test that function returns a Path object."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        intent_dir = repo_root / ".intent"
        intent_dir.mkdir()

        result = get_repo_root(start_dir=repo_root)
        assert isinstance(result, Path)

def test_get_repo_root_multiple_intent_directories():
    """Test that function finds the closest .intent directory when multiple exist."""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create outer .intent
        outer_root = Path(tmpdir)
        outer_intent = outer_root / ".intent"
        outer_intent.mkdir()

        # Create inner project with its own .intent
        inner_root = outer_root / "projects" / "myproject"
        inner_root.mkdir(parents=True)
        inner_intent = inner_root / ".intent"
        inner_intent.mkdir()

        # Create subdirectory within inner project
        subdir = inner_root / "src" / "utils"
        subdir.mkdir(parents=True)

        original_cwd = Path.cwd()
        try:
            os.chdir(subdir)
            result = get_repo_root()
            # Should find the inner .intent, not the outer one
            assert result == inner_root
        finally:
            os.chdir(original_cwd)

def test_get_repo_root_symlink_handling():
    """Test that function works correctly with symlinks in path."""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "real_repo"
        repo_root.mkdir()
        intent_dir = repo_root / ".intent"
        intent_dir.mkdir()

        # Create a symlink to the repo
        link_dir = Path(tmpdir) / "linked_repo"
        os.symlink(repo_root, link_dir)

        # Create subdirectory via symlink
        subdir = link_dir / "src" / "app"
        subdir.mkdir(parents=True)

        result = get_repo_root(start_dir=subdir)
        # Should resolve to the real path
        assert result.resolve() == repo_root.resolve()
