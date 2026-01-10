"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: copy_file
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:06:32
"""

import pytest
from pathlib import Path
from shared.path_utils import copy_file

# Detected return type: None (function performs file copy operation, returns nothing)

def test_copy_file_creates_destination_directory(tmp_path):
    """Test that copy_file creates parent directories when they don't exist."""
    src_file = tmp_path / "source.txt"
    src_file.write_text("Test content")

    # Destination in a non-existent subdirectory
    dst_file = tmp_path / "subdir" / "nested" / "destination.txt"

    # Directory should not exist yet
    assert not dst_file.parent.exists()

    copy_file(src_file, dst_file)

    # Directory should now exist
    assert dst_file.parent.exists()
    assert dst_file.exists()
    assert dst_file.read_text() == "Test content"

def test_copy_file_overwrites_existing_file(tmp_path):
    """Test that copy_file overwrites an existing destination file."""
    src_file = tmp_path / "source.txt"
    src_file.write_text("New content")

    dst_file = tmp_path / "destination.txt"
    dst_file.write_text("Old content")

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == "New content"

def test_copy_file_preserves_binary_content(tmp_path):
    """Test that copy_file correctly copies binary data."""
    binary_data = b'\x00\x01\x02\x03\xFF\xFE\xFD'
    src_file = tmp_path / "source.bin"
    src_file.write_bytes(binary_data)

    dst_file = tmp_path / "destination.bin"

    copy_file(src_file, dst_file)

    assert dst_file.read_bytes() == binary_data

def test_copy_file_with_empty_file(tmp_path):
    """Test that copy_file handles empty files correctly."""
    src_file = tmp_path / "empty.txt"
    src_file.write_text("")

    dst_file = tmp_path / "empty_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == ""
    assert dst_file.stat().st_size == 0

def test_copy_file_large_content(tmp_path):
    """Test that copy_file handles files with substantial content."""
    large_content = "A" * 10000 + "B" * 10000 + "Test with Unicode… character"
    src_file = tmp_path / "large.txt"
    src_file.write_text(large_content)

    dst_file = tmp_path / "large_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == large_content

def test_copy_file_same_path(tmp_path):
    """Test that copy_file can copy to the same location (overwrites itself)."""
    src_file = tmp_path / "self_copy.txt"
    original_content = "Original content with ellipsis…"
    src_file.write_text(original_content)

    # Copy to same path
    copy_file(src_file, src_file)

    # Should still contain the original content
    assert src_file.read_text() == original_content

def test_copy_file_preserves_existing_parent_directory(tmp_path):
    """Test that copy_file doesn't error when parent directory already exists."""
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()

    src_file = tmp_path / "source.txt"
    src_file.write_text("Test content")

    dst_file = existing_dir / "destination.txt"

    copy_file(src_file, dst_file)

    assert dst_file.exists()
    assert dst_file.read_text() == "Test content"

def test_copy_file_with_special_characters_in_filename(tmp_path):
    """Test that copy_file handles filenames with special characters."""
    src_file = tmp_path / "source_file_with_…_in_name.txt"
    content = "Content with special… characters"
    src_file.write_text(content)

    dst_file = tmp_path / "dest_file_with_…_in_name.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == content
