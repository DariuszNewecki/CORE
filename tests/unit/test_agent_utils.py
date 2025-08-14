# tests/unit/test_agent_utils.py
import re
import textwrap

import pytest
from agents.utils import CodeEditor


@pytest.fixture
def code_editor():
    """Provides an instance of the CodeEditor."""
    return CodeEditor()


@pytest.fixture
def sample_code():
    """Provides a sample Python code snippet for testing."""
    return textwrap.dedent(
        """
        # A sample file
        import os

        class MyClass:
            def method_one(self):
                \"\"\"This is the first method.\"\"\"
                return 1

        def top_level_function(a, b):
            \"\"\"A function at the top level.\"\"\"
            return a + b
    """
    )


def test_replace_simple_function(code_editor, sample_code):
    """Tests replacing a top-level function with a new version."""
    new_function_code = textwrap.dedent(
        """
        def top_level_function(a, b):
            \"\"\"A modified function.\"\"\"
            # Added a comment
            return a * b  # Changed the operation
    """
    )
    modified_code = code_editor.replace_symbol_in_code(
        sample_code, "top_level_function", new_function_code
    )

    assert "return a * b" in modified_code
    assert "return a + b" not in modified_code
    assert "class MyClass:" in modified_code
    assert "method_one" in modified_code
    assert "# A sample file" in modified_code  # Check that comments are preserved


def test_replace_method_in_class(code_editor, sample_code):
    """Tests replacing a method within a class."""
    new_method_code = textwrap.dedent(
        """
        def method_one(self):
            \"\"\"A new docstring for the method.\"\"\"
            return 100
    """
    )
    modified_code = code_editor.replace_symbol_in_code(
        sample_code, "method_one", new_method_code
    )

    assert "return 100" in modified_code
    # Ensure there's no standalone "return 1" line (avoid substring false positives)
    assert not re.search(r"(?m)^\s*return\s+1\s*$", modified_code)
    assert "top_level_function" in modified_code
    # Crucially, check that the class definition is still present
    assert "class MyClass:" in modified_code


def test_replace_symbol_not_found_raises_error(code_editor, sample_code):
    """Tests that a ValueError is raised if the target symbol doesn't exist."""
    new_code = "def new_func(): return None"
    with pytest.raises(ValueError, match="Symbol 'non_existent_function' not found"):
        code_editor.replace_symbol_in_code(
            sample_code, "non_existent_function", new_code
        )


def test_replace_with_invalid_original_syntax_raises_error(code_editor):
    """Tests that a ValueError is raised if the original code has a syntax error."""
    invalid_original_code = "def top_level_function(a, b) return a + b"
    new_code = "def top_level_function(a,b): return a*b"
    with pytest.raises(
        ValueError, match="Could not parse original code due to syntax error"
    ):
        code_editor.replace_symbol_in_code(
            invalid_original_code, "top_level_function", new_code
        )
