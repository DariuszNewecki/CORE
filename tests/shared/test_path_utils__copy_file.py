"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: copy_file
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:50:52
"""

import pytest
from pathlib import Path
from shared.path_utils import copy_file

# Detected return type: None (function performs file copy operation)

def test_copy_file_creates_destination_directory(tmp_path):
    """Test that copy_file creates parent directories when they don't exist."""
    src_file = tmp_path / "source.txt"
    src_file.write_text("Test content")

    # Destination in a non-existent subdirectory
    dst_file = tmp_path / "subdir" / "nested" / "destination.txt"

    # Verify directory doesn't exist initially
    assert not dst_file.parent.exists()

    copy_file(src_file, dst_file)

    # Verify directory was created and file was copied
    assert dst_file.parent.exists()
    assert dst_file.read_text() == "Test content"

def test_copy_file_overwrites_existing_file(tmp_path):
    """Test that copy_file overwrites an existing destination file."""
    src_file = tmp_path / "source.txt"
    src_file.write_text("New content")

    dst_file = tmp_path / "destination.txt"
    dst_file.write_text("Old content")  # Existing file

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
    src_file.write_text("")  # Empty file

    dst_file = tmp_path / "empty_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == ""
    assert dst_file.stat().st_size == 0

def test_copy_file_unicode_content(tmp_path):
    """Test that copy_file handles Unicode text correctly."""
    unicode_content = "Hello World… Unicode: café, résumé, naïve"  # Using Unicode ellipsis
    src_file = tmp_path / "unicode.txt"
    src_file.write_text(unicode_content)

    dst_file = tmp_path / "unicode_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == unicode_content

def test_copy_file_large_content(tmp_path):
    """Test that copy_file handles larger files correctly."""
    large_content = "X" * 10000  # 10KB of data
    src_file = tmp_path / "large.txt"
    src_file.write_text(large_content)

    dst_file = tmp_path / "large_copy.txt"

    copy_file(src_file, dst_file)

    assert dst_file.read_text() == large_content
    assert src_file.stat().st_size == dst_file.stat().st_size

def test_copy_file_same_path(tmp_path):
    """Test that copy_file can overwrite the source file (same path)."""
    src_file = tmp_path / "file.txt"
    src_file.write_text("Original")

    # Copy to same path - should overwrite with same content
    copy_file(src_file, src_file)

    # File should still exist with original content
    assert src_file.exists()
    assert src_file.read_text() == "Original"

def test_copy_file_preserves_file_metadata_separately(tmp_path):
    """Test that copy_file creates independent file (changes to one don't affect the other)."""
    src_file = tmp_path / "original.txt"
    src_file.write_text("First version")

    dst_file = tmp_path / "copy.txt"

    copy_file(src_file, dst_file)

    # Modify source file after copy
    src_file.write_text("Modified source")

    # Destination should still have original content
    assert dst_file.read_text() == "First version"
    assert src_file.read_text() == "Modified source"
