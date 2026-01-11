"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: copy_tree
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:51:17
"""

import pytest
from pathlib import Path
from shared.path_utils import copy_tree

# The function 'copy_tree' is a regular 'def' function, not 'async def'.
# It returns None. Tests will be standard 'def' functions.

def test_copy_tree_creates_destination(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "file.txt").write_text("content")
    copy_tree(src, dst, exclude=[])
    assert dst.exists()
    assert (dst / "file.txt").exists()
    assert (dst / "file.txt").read_text() == "content"

def test_copy_tree_excludes_default_directories(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "file.txt").write_text("content")
    (src / ".git").mkdir()
    (src / "__pycache__").mkdir()
    copy_tree(src, dst)  # Use default exclude
    assert (dst / "file.txt").exists()
    assert not (dst / ".git").exists()
    assert not (dst / "__pycache__").exists()

def test_copy_tree_excludes_custom_list(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "keep.txt").write_text("keep")
    (src / "skipdir").mkdir()
    (src / "skipdir" / "inside.txt").write_text("inside")
    copy_tree(src, dst, exclude=["skipdir"])
    assert (dst / "keep.txt").exists()
    assert not (dst / "skipdir").exists()

def test_copy_tree_recursive_copy(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "subdir").mkdir()
    (src / "subdir" / "nested.txt").write_text("nested")
    (src / "top.txt").write_text("top")
    copy_tree(src, dst, exclude=[])
    assert (dst / "subdir").exists()
    assert (dst / "subdir" / "nested.txt").read_text() == "nested"
    assert (dst / "top.txt").read_text() == "top"

def test_copy_tree_destination_parents_created(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "deep" / "nested" / "dest"
    src.mkdir()
    (src / "test.txt").write_text("test")
    copy_tree(src, dst, exclude=[])
    assert dst.exists()
    assert (dst / "test.txt").exists()

def test_copy_tree_empty_source_dir(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    copy_tree(src, dst, exclude=[])
    assert dst.exists()
    # Should contain no files, only the directory itself
    assert list(dst.iterdir()) == []

def test_copy_tree_exclude_applies_to_all_levels(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "venv").mkdir()
    (src / "venv" / "file.txt").write_text("in venv")
    (src / "sub").mkdir()
    (src / "sub" / "venv").mkdir()
    (src / "sub" / "venv" / "deep.txt").write_text("deep")
    (src / "sub" / "keep.txt").write_text("keep")
    copy_tree(src, dst)  # Default exclude includes "venv"
    assert not (dst / "venv").exists()
    assert (dst / "sub").exists()
    assert not (dst / "sub" / "venv").exists()
    assert (dst / "sub" / "keep.txt").read_text() == "keep"
