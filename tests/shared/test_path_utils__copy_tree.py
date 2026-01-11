"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/path_utils.py
- Symbol: copy_tree
- Status: 1 tests passed, some failed
- Passing tests: test_copy_tree_source_is_file_not_directory
- Generated: 2026-01-11 10:43:56
"""

import pytest

from shared.path_utils import copy_tree


def test_copy_tree_source_is_file_not_directory(tmp_path):
    """Test behavior when source is a file (should raise error or handle gracefully)."""
    src_file = tmp_path / "source.txt"
    dst_dir = tmp_path / "destination"
    src_file.write_text("file content")
    with pytest.raises((AttributeError, NotADirectoryError)):
        copy_tree(src_file, dst_dir)
