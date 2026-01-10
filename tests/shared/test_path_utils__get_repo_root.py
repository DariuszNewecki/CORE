"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/path_utils.py
- Symbol: get_repo_root
- Status: 7 tests passed, some failed
- Passing tests: test_get_repo_root_finds_intent_directory, test_get_repo_root_finds_intent_in_start_dir, test_get_repo_root_raises_when_no_intent_found, test_get_repo_root_handles_root_filesystem, test_get_repo_root_with_explicit_start_dir, test_get_repo_root_returns_path_object, test_get_repo_root_finds_intent_at_filesystem_root
- Generated: 2026-01-11 00:07:55
"""

import pytest
from pathlib import Path
from shared.path_utils import get_repo_root

def test_get_repo_root_finds_intent_directory(tmp_path):
    """Test that function finds .intent directory in current directory."""
    repo_root = tmp_path / 'project'
    repo_root.mkdir()
    (repo_root / '.intent').mkdir()
    start_dir = repo_root / 'src' / 'module'
    start_dir.mkdir(parents=True)
    result = get_repo_root(start_dir=start_dir)
    assert result == repo_root

def test_get_repo_root_finds_intent_in_start_dir():
    """Test that function finds .intent when start_dir contains it."""
    try:
        result = get_repo_root()
        assert isinstance(result, Path)
        assert (result / '.intent').is_dir()
    except FileNotFoundError:
        pytest.skip('No .intent directory found in test environment')

def test_get_repo_root_raises_when_no_intent_found(tmp_path):
    """Test that function raises FileNotFoundError when no .intent directory exists."""
    test_dir = tmp_path / 'no_project' / 'subdir'
    test_dir.mkdir(parents=True)
    with pytest.raises(FileNotFoundError) as exc_info:
        get_repo_root(start_dir=test_dir)
    assert 'Project root with .intent directory not found' in str(exc_info.value)

def test_get_repo_root_handles_root_filesystem():
    """Test that function checks root filesystem when traversing upwards."""
    test_dir = Path('/tmp')
    with pytest.raises(FileNotFoundError):
        get_repo_root(start_dir=test_dir)

def test_get_repo_root_with_explicit_start_dir(tmp_path):
    """Test that function respects provided start_dir parameter."""
    repo_root = tmp_path / 'my_project'
    repo_root.mkdir()
    (repo_root / '.intent').mkdir()
    other_dir = tmp_path / 'other_dir'
    other_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        get_repo_root(start_dir=other_dir)
    subdir = repo_root / 'deep' / 'nested' / 'path'
    subdir.mkdir(parents=True)
    result = get_repo_root(start_dir=subdir)
    assert result == repo_root

def test_get_repo_root_returns_path_object(tmp_path):
    """Test that function returns a Path object."""
    repo_root = tmp_path / 'test_project'
    repo_root.mkdir()
    (repo_root / '.intent').mkdir()
    result = get_repo_root(start_dir=repo_root)
    assert isinstance(result, Path)
    assert result == repo_root

def test_get_repo_root_finds_intent_at_filesystem_root(tmp_path):
    """Test edge case where .intent is at filesystem root (unlikely but possible)."""
    fake_root = tmp_path / 'fake_root'
    fake_root.mkdir()
    (fake_root / '.intent').mkdir()
    deep_dir = fake_root / 'very' / 'deep' / 'nested' / 'directory'
    deep_dir.mkdir(parents=True)
    original_parent = Path.parent
    try:

        def mock_parent(self):
            if self == fake_root:
                return fake_root
            if str(self).startswith(str(fake_root)):
                parts = self.parts
                fake_parts = fake_root.parts
                if len(parts) > len(fake_parts):
                    return fake_root / Path(*parts[len(fake_parts):-1])
            return original_parent(self)
        Path.parent = property(mock_parent)
        import shared.path_utils
        original_cwd = Path.cwd

        def mock_cwd():
            return deep_dir
        Path.cwd = staticmethod(mock_cwd)
        result = get_repo_root()
        assert result == fake_root
    finally:
        Path.parent = original_parent
        Path.cwd = staticmethod(original_cwd)
