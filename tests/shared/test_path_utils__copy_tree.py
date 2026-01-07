"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: copy_tree
- Status: verified_in_sandbox
- Generated: 2026-01-07 22:11:19
"""

import pytest

from shared.path_utils import copy_tree


# Detected return type: None (function performs side effects, copying files and directories)


def test_copy_tree_basic_directory_structure(tmp_path):
    """Test copying a simple directory tree."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "file1.txt").write_text("content1")
    (src / "subdir").mkdir()
    (src / "subdir" / "file2.txt").write_text("content2")

    copy_tree(src, dst, exclude=[])

    assert (dst / "file1.txt").exists()
    assert (dst / "file1.txt").read_text() == "content1"
    assert (dst / "subdir").exists()
    assert (dst / "subdir" / "file2.txt").exists()
    assert (dst / "subdir" / "file2.txt").read_text() == "content2"


def test_copy_tree_with_default_exclude(tmp_path):
    """Test that default excluded directories are not copied."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "normal.txt").write_text("ok")
    (src / ".git").mkdir()
    (src / ".git" / "config").write_text("gitdata")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "module.cpython-310.pyc").write_text("bytecode")

    copy_tree(src, dst)

    assert (dst / "normal.txt").exists()
    assert not (dst / ".git").exists()
    assert not (dst / "__pycache__").exists()


def test_copy_tree_with_custom_exclude_list(tmp_path):
    """Test copying with a custom exclude list."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "keep.txt").write_text("keep")
    (src / "skipme").mkdir()
    (src / "skipme" / "inside.txt").write_text("inside")
    (src / "keepdir").mkdir()
    (src / "keepdir" / "file.txt").write_text("file")

    copy_tree(src, dst, exclude=["skipme"])

    assert (dst / "keep.txt").exists()
    assert not (dst / "skipme").exists()
    assert (dst / "keepdir").exists()
    assert (dst / "keepdir" / "file.txt").exists()


def test_copy_tree_empty_source_directory(tmp_path):
    """Test copying an empty directory."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()

    copy_tree(src, dst, exclude=[])

    assert dst.exists()
    # Ensure no files were created in dest
    assert list(dst.iterdir()) == []


def test_copy_tree_destination_exists(tmp_path):
    """Test copying into an existing destination directory."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    dst.mkdir()
    (src / "new.txt").write_text("new")
    (dst / "existing.txt").write_text("old")

    copy_tree(src, dst, exclude=[])

    # New file is added
    assert (dst / "new.txt").exists()
    assert (dst / "new.txt").read_text() == "new"
    # Existing file is preserved (not overwritten by copy_tree, though copy_file might)
    assert (dst / "existing.txt").exists()


def test_copy_tree_exclude_none_uses_default(tmp_path):
    """Test that exclude=None triggers the default exclude list."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "file.txt").write_text("ok")
    (src / ".venv").mkdir()
    (src / ".venv" / "pyvenv.cfg").write_text("config")

    copy_tree(src, dst, exclude=None)

    assert (dst / "file.txt").exists()
    assert not (dst / ".venv").exists()


def test_copy_tree_nested_exclusion(tmp_path):
    """Test that excluded directory names are skipped at any nesting level."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    (src / "project").mkdir()
    (src / "project" / "__pycache__").mkdir()
    (src / "project" / "__pycache__" / "test.pyc").write_text("data")
    (src / "project" / "src").mkdir()
    (src / "project" / "src" / "__pycache__").mkdir()
    (src / "project" / "src" / "__pycache__" / "another.pyc").write_text("more")

    copy_tree(src, dst)

    assert (dst / "project").exists()
    assert not (dst / "project" / "__pycache__").exists()
    assert (dst / "project" / "src").exists()
    assert not (dst / "project" / "src" / "__pycache__").exists()


def test_copy_tree_symlinks_and_special_files(tmp_path):
    """Test behavior with symlinks (should be followed as normal files by copy_file)."""
    src = tmp_path / "source"
    dst = tmp_path / "dest"
    src.mkdir()
    target = src / "target.txt"
    target.write_text("actual content")
    link = src / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this system")
    # Symlink should be copied as a file with the target's content
    copy_tree(src, dst, exclude=[])
    assert (dst / "link.txt").exists()
    # The copy_file helper should have dereferenced the symlink
    assert (dst / "link.txt").read_text() == "actual content"
