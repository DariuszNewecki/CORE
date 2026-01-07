"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_utils.py
- Symbol: copy_file
- Status: verified_in_sandbox
- Generated: 2026-01-07 22:10:41
"""

from shared.path_utils import copy_file


# Detected return type: None (function performs a side effect)


def test_copy_file_creates_destination_directory(tmp_path):
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    src_file = src_dir / "test.txt"
    src_content = b"File content"
    src_file.write_bytes(src_content)

    dst_dir = tmp_path / "dest" / "subdir"
    dst_file = dst_dir / "copied.txt"

    copy_file(src_file, dst_file)

    assert dst_file.exists()
    assert dst_file.read_bytes() == src_content


def test_copy_file_overwrites_existing(tmp_path):
    src_file = tmp_path / "src.txt"
    src_file.write_bytes(b"New content")

    dst_file = tmp_path / "dst.txt"
    dst_file.write_bytes(b"Old content")

    copy_file(src_file, dst_file)

    assert dst_file.read_bytes() == b"New content"


def test_copy_file_preserves_exact_bytes(tmp_path):
    binary_data = b"\x00\x01\x02\x03\xff\xfe\xfd"
    src_file = tmp_path / "source.bin"
    src_file.write_bytes(binary_data)

    dst_file = tmp_path / "dest.bin"
    copy_file(src_file, dst_file)

    assert dst_file.read_bytes() == binary_data


def test_copy_file_parent_exists_no_error(tmp_path):
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    src_file = tmp_path / "src.txt"
    src_file.write_bytes(b"data")

    dst_file = existing_dir / "copy.txt"
    copy_file(src_file, dst_file)

    assert dst_file.exists()
