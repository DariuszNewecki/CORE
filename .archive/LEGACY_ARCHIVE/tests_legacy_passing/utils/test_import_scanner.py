# tests/shared/utils/test_import_scanner.py
"""Tests for import_scanner module."""

from shared.utils.import_scanner import scan_imports_for_file


class TestScanImportsForFile:
    """Tests for scan_imports_for_file function."""

    def test_scans_simple_imports(self, tmp_path):
        """Test scanning simple import statements."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os\nimport sys")

        imports = scan_imports_for_file(test_file)

        assert "os" in imports
        assert "sys" in imports
        assert len(imports) == 2

    def test_scans_from_imports(self, tmp_path):
        """Test scanning 'from X import Y' statements."""
        test_file = tmp_path / "test.py"
        test_file.write_text("from pathlib import Path\nfrom os.path import join")

        imports = scan_imports_for_file(test_file)

        assert "pathlib" in imports
        assert "os.path" in imports

    def test_scans_multiple_names_in_import(self, tmp_path):
        """Test import with multiple names."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import os, sys, json")

        imports = scan_imports_for_file(test_file)

        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports

    def test_scans_aliased_imports(self, tmp_path):
        """Test imports with aliases."""
        test_file = tmp_path / "test.py"
        test_file.write_text("import numpy as np\nfrom pathlib import Path as P")

        imports = scan_imports_for_file(test_file)

        assert "numpy" in imports
        assert "pathlib" in imports

    def test_ignores_code_body(self, tmp_path):
        """Test that only top-level imports are captured."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
import os

def foo():
    import sys
    return sys.path

import json
"""
        )

        imports = scan_imports_for_file(test_file)

        # Should capture all imports including nested ones (ast.walk gets all)
        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports

    def test_handles_empty_file(self, tmp_path):
        """Test scanning empty file."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("")

        imports = scan_imports_for_file(test_file)

        assert imports == []

    def test_handles_file_with_no_imports(self, tmp_path):
        """Test file with code but no imports."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'")

        imports = scan_imports_for_file(test_file)

        assert imports == []

    def test_handles_syntax_error_gracefully(self, tmp_path):
        """Test that syntax errors are handled gracefully."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("import os\ndef broken(\n    pass")

        imports = scan_imports_for_file(test_file)

        # Should return empty list on error
        assert imports == []

    def test_handles_missing_file_gracefully(self, tmp_path):
        """Test that missing file doesn't crash."""
        nonexistent = tmp_path / "nonexistent.py"

        imports = scan_imports_for_file(nonexistent)

        assert imports == []

    def test_handles_unicode_in_file(self, tmp_path):
        """Test file with unicode characters."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            "# -*- coding: utf-8 -*-\nimport os\n# Comment with émojis 😀"
        )

        imports = scan_imports_for_file(test_file)

        assert "os" in imports

    def test_scans_from_import_without_module(self, tmp_path):
        """Test 'from . import X' relative import."""
        test_file = tmp_path / "test.py"
        test_file.write_text("from . import something\nimport os")

        imports = scan_imports_for_file(test_file)

        # Relative imports have node.module = None, so not captured
        assert "os" in imports

    def test_complex_import_combinations(self, tmp_path):
        """Test file with various import styles."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            """
import os
import sys, json
from pathlib import Path
from typing import List, Dict
from collections.abc import Iterable
"""
        )

        imports = scan_imports_for_file(test_file)

        assert "os" in imports
        assert "sys" in imports
        assert "json" in imports
        assert "pathlib" in imports
        assert "typing" in imports
        assert "collections.abc" in imports
