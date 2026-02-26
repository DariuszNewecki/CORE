# tests/shared/utils/test_path_utils.py

import pytest


pytestmark = pytest.mark.legacy

from shared.path_utils import copy_file, copy_tree, get_repo_root


def test_copy_file_creates_parent_dirs(tmp_path):
    """Test that copy_file handles nested directories correctly."""
    src = tmp_path / "source.txt"
    src.write_text("content")

    dst = tmp_path / "deep" / "nested" / "dest.txt"

    copy_file(src, dst)

    assert dst.exists()
    assert dst.read_text() == "content"


def test_copy_tree_recursive_and_excludes(tmp_path):
    """Test that copy_tree works recursively and respects exclusions."""
    src = tmp_path / "src_root"
    src.mkdir()

    # Regular files
    (src / "root.txt").write_text("root")
    (src / "sub").mkdir()
    (src / "sub" / "nested.txt").write_text("nested")

    # Excluded files (default exclusions include .git and __pycache__)
    (src / ".git").mkdir()
    (src / ".git" / "config").write_text("secret")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "cache.pyc").write_text("binary")

    dst = tmp_path / "dst_root"

    copy_tree(src, dst)

    # Verify success
    assert (dst / "root.txt").read_text() == "root"
    assert (dst / "sub" / "nested.txt").read_text() == "nested"

    # Verify exclusions
    assert not (dst / ".git").exists()
    assert not (dst / "__pycache__").exists()


def test_get_repo_root_finds_intent(tmp_path):
    """Test that get_repo_root finds the .intent directory."""
    (tmp_path / ".intent").mkdir()

    # Start searching from a deep subdirectory
    start_dir = tmp_path / "src" / "deep"
    start_dir.mkdir(parents=True)

    root = get_repo_root(start_dir)
    assert root == tmp_path


def test_get_repo_root_fails_without_intent(tmp_path):
    """Test that FileNotFoundError is raised if .intent is missing."""
    with pytest.raises(FileNotFoundError):
        get_repo_root(tmp_path)
