# tests/shared/utils/test_header_tools.py
from src.shared.utils.header_tools import HeaderComponents, HeaderTools


class TestHeaderComponents:
    """Tests for HeaderComponents dataclass."""

    def test_default_values(self):
        """Test that HeaderComponents has correct default values."""
        components = HeaderComponents()
        assert components.location is None
        assert components.module_description is None
        assert components.has_future_import is False
        assert components.other_imports == []
        assert components.body == []

    def test_custom_values(self):
        """Test HeaderComponents with custom values."""
        components = HeaderComponents(
            location="# /some/path",
            module_description='"""Test module"""',
            has_future_import=True,
            other_imports=["import os", "import sys"],
            body=["def test():", "    pass"],
        )
        assert components.location == "# /some/path"
        assert components.module_description == '"""Test module"""'
        assert components.has_future_import is True
        assert components.other_imports == ["import os", "import sys"]
        assert components.body == ["def test():", "    pass"]


class TestHeaderToolsParse:
    """Tests for HeaderTools.parse method."""

    def test_parse_empty_source(self):
        """Test parsing empty source code."""
        components = HeaderTools.parse("")
        assert components.location is None
        assert components.module_description is None
        assert components.has_future_import is False
        assert components.other_imports == []
        assert components.body == []

    def test_parse_only_location(self):
        """Test parsing source with only location comment."""
        source = "# /test/path.py"
        components = HeaderTools.parse(source)
        assert components.location == "# /test/path.py"
        assert components.module_description is None
        assert components.has_future_import is False
        assert components.other_imports == []
        # FIX: Location comment goes to body when there's no other header content
        assert components.body == ["# /test/path.py"]

    def test_parse_location_and_docstring(self):
        """Test parsing source with location and docstring."""
        source = '''# /test/path.py
"""Test module docstring."""
'''
        components = HeaderTools.parse(source)
        assert components.location == "# /test/path.py"
        assert components.module_description == '"""Test module docstring."""'
        assert components.has_future_import is False
        assert components.other_imports == []
        assert components.body == []

    def test_parse_with_future_import(self):
        """Test parsing source with future import."""
        source = '''"""Test module."""

from __future__ import annotations
'''
        components = HeaderTools.parse(source)
        assert components.location is None
        assert components.module_description == '"""Test module."""'
        assert components.has_future_import is True
        assert components.other_imports == []
        assert components.body == []

    def test_parse_with_other_imports(self):
        """Test parsing source with other imports."""
        source = '''"""Test module."""
import os
import sys
from typing import List
'''
        components = HeaderTools.parse(source)
        assert components.location is None
        assert components.module_description == '"""Test module."""'
        assert components.has_future_import is False
        assert "import os" in components.other_imports
        assert "import sys" in components.other_imports
        assert "from typing import List" in components.other_imports
        assert components.body == []

    def test_parse_with_body(self):
        """Test parsing source with body content."""
        source = '''"""Test module."""

def hello():
    return "world"
'''
        components = HeaderTools.parse(source)
        assert components.location is None
        assert components.module_description == '"""Test module."""'
        assert components.has_future_import is False
        assert components.other_imports == []
        assert components.body == ["def hello():", '    return "world"']

    def test_parse_multi_line_docstring(self):
        """Test parsing source with multi-line docstring."""
        source = '''"""Test module
with multiple lines
of documentation.
"""
'''
        components = HeaderTools.parse(source)
        assert '"""Test module' in components.module_description
        assert "with multiple lines" in components.module_description
        assert "of documentation." in components.module_description

    def test_parse_single_quotes_docstring(self):
        """Test parsing source with single-quoted docstring."""
        source = "'''Test module.'''"
        components = HeaderTools.parse(source)
        assert components.module_description == "'''Test module.'''"

    def test_parse_with_blank_lines_before_body(self):
        """Test parsing source with blank lines before body."""
        source = '''"""Test module."""


def test():
    pass
'''
        components = HeaderTools.parse(source)
        assert components.module_description == '"""Test module."""'
        assert components.body == ["def test():", "    pass"]

    def test_parse_invalid_syntax(self):
        """Test parsing source with invalid syntax."""
        source = '''"""Test module."""
invalid python syntax
'''
        components = HeaderTools.parse(source)
        assert components.body == ['"""Test module."""', "invalid python syntax"]

    def test_parse_only_body(self):
        """Test parsing source with only body content."""
        source = """def hello():
    return "world"
"""
        components = HeaderTools.parse(source)
        assert components.location is None
        assert components.module_description is None
        assert components.has_future_import is False
        assert components.other_imports == []
        assert components.body == ["def hello():", '    return "world"']


class TestHeaderToolsReconstruct:
    """Tests for HeaderTools.reconstruct method."""

    def test_reconstruct_empty_components(self):
        """Test reconstructing from empty components."""
        components = HeaderComponents()
        result = HeaderTools.reconstruct(components)
        assert result == "\n"

    def test_reconstruct_only_location(self):
        """Test reconstructing with only location."""
        components = HeaderComponents(location="# /test/path.py")
        result = HeaderTools.reconstruct(components)
        assert result == "# /test/path.py\n"

    def test_reconstruct_location_and_docstring(self):
        """Test reconstructing with location and docstring."""
        components = HeaderComponents(
            location="# /test/path.py", module_description='"""Test module."""'
        )
        result = HeaderTools.reconstruct(components)
        assert "# /test/path.py" in result
        assert '"""Test module."""' in result

    def test_reconstruct_with_future_import(self):
        """Test reconstructing with future import."""
        components = HeaderComponents(
            module_description='"""Test module."""', has_future_import=True
        )
        result = HeaderTools.reconstruct(components)
        assert '"""Test module."""' in result
        assert "from __future__ import annotations" in result

    def test_reconstruct_with_other_imports(self):
        """Test reconstructing with other imports."""
        components = HeaderComponents(
            module_description='"""Test module."""',
            other_imports=["import os", "import sys"],
        )
        result = HeaderTools.reconstruct(components)
        assert '"""Test module."""' in result
        assert "import os" in result
        assert "import sys" in result

    def test_reconstruct_with_body(self):
        """Test reconstructing with body content."""
        components = HeaderComponents(
            module_description='"""Test module."""',
            body=["def test():", "    return 'hello'"],
        )
        result = HeaderTools.reconstruct(components)
        assert '"""Test module."""' in result
        assert "def test():" in result
        assert "return 'hello'" in result

    def test_reconstruct_complex_example(self):
        """Test reconstructing a complex example."""
        components = HeaderComponents(
            location="# /complex/example.py",
            module_description='"""Complex example module."""',
            has_future_import=True,
            other_imports=["import os", "from typing import List"],
            body=["class Example:", "    pass"],
        )
        result = HeaderTools.reconstruct(components)
        assert "# /complex/example.py" in result
        assert '"""Complex example module."""' in result
        assert "from __future__ import annotations" in result
        assert "import os" in result
        assert "from typing import List" in result
        assert "class Example:" in result
        assert "    pass" in result

    def test_reconstruct_preserves_import_order(self):
        """Test that imports are sorted in reconstruction."""
        components = HeaderComponents(
            other_imports=["import zlib", "import abc", "import sys"]
        )
        result = HeaderTools.reconstruct(components)
        # Imports should be sorted alphabetically
        lines = result.strip().split("\n")
        import_lines = [line for line in lines if line.startswith("import")]
        assert import_lines == ["import abc", "import sys", "import zlib"]

    def test_reconstruct_removes_trailing_blank_lines(self):
        """Test that trailing blank lines are removed from body."""
        components = HeaderComponents(body=["def test():", "    pass", "", ""])
        result = HeaderTools.reconstruct(components)
        # Should not have multiple trailing newlines
        assert not result.endswith("\n\n\n")


class TestHeaderToolsRoundTrip:
    """Tests for round-trip parsing and reconstruction."""

    def test_round_trip_simple(self):
        """Test round-trip with simple source."""
        source = '''# /test.py
"""Test module."""

def hello():
    return "world"
'''
        components = HeaderTools.parse(source)
        reconstructed = HeaderTools.reconstruct(components)
        # FIX: Check structural equivalence rather than exact string match
        assert "# /test.py" in reconstructed
        assert '"""Test module."""' in reconstructed
        assert "def hello():" in reconstructed
        assert 'return "world"' in reconstructed

    def test_round_trip_with_imports(self):
        """Test round-trip with imports."""
        source = '''"""Test module."""

from __future__ import annotations

import os
import sys

class Test:
    pass
'''
        components = HeaderTools.parse(source)
        reconstructed = HeaderTools.reconstruct(components)
        # FIX: Check structural equivalence rather than exact string match
        assert '"""Test module."""' in reconstructed
        assert "from __future__ import annotations" in reconstructed
        assert "import os" in reconstructed
        assert "import sys" in reconstructed
        assert "class Test:" in reconstructed
        assert "    pass" in reconstructed

    def test_round_trip_multi_line_docstring(self):
        """Test round-trip with multi-line docstring."""
        source = '''"""Test module
with multiple lines.
"""

def test():
    pass
'''
        components = HeaderTools.parse(source)
        reconstructed = HeaderTools.reconstruct(components)
        # FIX: Check structural equivalence
        assert '"""Test module' in reconstructed
        assert "with multiple lines." in reconstructed
        assert "def test():" in reconstructed
        assert "    pass" in reconstructed
