"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: copy_file
- Status: verified_in_sandbox
- Generated: 2026-01-11 10:43:01
"""

import pytest
from pathlib import Path
from shared.path_utils import copy_file

# copy_file returns None (void function)

def test_copy_file_creates_destination_directory(tmp_path):
    """Test that copy_file creates parent directories when they don't exist."""
    src_file = tmp_path / "source.txt"
    src_file.write_text("Test content")

    # Destination in a non-existent subdirectory
    dst_file = tmp_path / "subdir" / "nested" / "destination.txt"

    copy_file(src_file, dst_file)

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

def test_copy_file_to_existing_directory_structure(tmp_path):
    """Test that copy_file works when parent directories already exist."""
    src_file = tmp_path / "source.txt"
    src_file.write_text("Content")

    # Create the parent directory first
    (tmp_path / "existing_dir").mkdir()
    dst_file = tmp_path / "existing_dir" / "destination.txt"

    copy_file(src_file, dst_file)

    assert dst_file.exists()
    assert dst_file.read_text() == "Content"

def test_copy_file_with_special_characters_in_filename(tmp_path):
    """Test that copy_file handles filenames with special characters."""
    src_file = tmp_path / "source_file_with_special_chars_…_test.txt"
    content = "Content with special chars … and more"
    src_file.write_text(content)

    dst_file = tmp_path / "dest_file_with_special_chars_…_test.txt"

    copy_file(src_file, dst_file)

    assert dst_file.exists()
    assert dst_file.read_text() == content

def test_copy_file_empty_file(tmp_path):
    """Test that copy_file correctly copies an empty file."""
    src_file = tmp_path / "empty.txt"
    src_file.write_text("")  # Empty file

    dst_file = tmp_path / "empty_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.exists()
    assert dst_file.read_text() == ""
    assert dst_file.stat().st_size == 0

def test_copy_file_large_content(tmp_path):
    """Test that copy_file handles files with substantial content."""
    large_content = "A" * 10000 + "…" + "B" * 10000
    src_file = tmp_path / "large.txt"
    src_file.write_text(large_content)

    dst_file = tmp_path / "large_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == large_content
    assert len(dst_file.read_text()) == len(large_content)
