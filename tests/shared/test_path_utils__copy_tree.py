"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/path_utils.py
- Symbol: copy_tree
- Status: 1 tests passed, some failed
- Passing tests: test_copy_tree_empty_source_directory
- Generated: 2026-01-11 00:07:18
"""

import pytest
from pathlib import Path
from shared.path_utils import copy_tree

def test_copy_tree_empty_source_directory(tmp_path):
    """Test copying an empty directory."""
    src = tmp_path / 'source'
    dst = tmp_path / 'destination'
    src.mkdir()
    copy_tree(src, dst)
    assert dst.exists()
    assert dst.is_dir()
    assert list(dst.iterdir()) == []
