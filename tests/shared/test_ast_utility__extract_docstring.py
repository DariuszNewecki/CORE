"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/ast_utility.py
- Symbol: extract_docstring
- Status: 10 tests passed, some failed
- Passing tests: test_extract_docstring_from_function_def, test_extract_docstring_from_async_function_def, test_extract_docstring_from_class_def, test_extract_docstring_from_module, test_extract_docstring_no_docstring, test_extract_docstring_empty_docstring, test_extract_docstring_multiline_docstring, test_extract_docstring_unsupported_node_type, test_extract_docstring_expression_statement, test_extract_docstring_triple_single_quotes
- Generated: 2026-01-11 01:09:43
"""

import pytest
from shared.ast_utility import extract_docstring
import ast

def test_extract_docstring_from_function_def():
    """Test extracting docstring from a regular function definition."""
    source = '\ndef my_function():\n    """This is a docstring."""\n    pass\n'
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_docstring(func_node)
    expected = 'This is a docstring.'
    assert result == expected

def test_extract_docstring_from_async_function_def():
    """Test extracting docstring from an async function definition."""
    source = '\nasync def my_async_function():\n    """Async function docstring."""\n    pass\n'
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_docstring(func_node)
    expected = 'Async function docstring.'
    assert result == expected

def test_extract_docstring_from_class_def():
    """Test extracting docstring from a class definition."""
    source = '\nclass MyClass:\n    """Class docstring here."""\n    def method(self):\n        pass\n'
    tree = ast.parse(source)
    class_node = tree.body[0]
    result = extract_docstring(class_node)
    expected = 'Class docstring here.'
    assert result == expected

def test_extract_docstring_from_module():
    """Test extracting docstring from a module (top-level)."""
    source = '\n"""Module-level docstring."""\ndef some_function():\n    pass\n'
    tree = ast.parse(source)
    result = extract_docstring(tree)
    expected = 'Module-level docstring.'
    assert result == expected

def test_extract_docstring_no_docstring():
    """Test node with no docstring returns None."""
    source = '\ndef no_docstring():\n    pass\n'
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_docstring(func_node)
    assert result is None

def test_extract_docstring_empty_docstring():
    """Test node with empty docstring returns empty string."""
    source = '\ndef empty_docstring():\n    ""\n    pass\n'
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_docstring(func_node)
    assert result == ''

def test_extract_docstring_multiline_docstring():
    """Test extracting multiline docstring."""
    source = '\ndef multiline_func():\n    """First line.\n    \n    Second line with more details.\n    \n    Returns:\n        Nothing.\n    """\n    pass\n'
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_docstring(func_node)
    expected = 'First line.\n\nSecond line with more details.\n\nReturns:\n    Nothing.'
    assert result == expected

def test_extract_docstring_unsupported_node_type():
    """Test that non-docstring nodes return None."""
    source = '\nx = 5\n'
    tree = ast.parse(source)
    assign_node = tree.body[0]
    result = extract_docstring(assign_node)
    assert result is None

def test_extract_docstring_expression_statement():
    """Test expression statement (not supported type) returns None."""
    source = '\ncall_something()\n'
    tree = ast.parse(source)
    expr_node = tree.body[0]
    result = extract_docstring(expr_node)
    assert result is None

def test_extract_docstring_triple_single_quotes():
    """Test docstring with triple single quotes."""
    source = "\ndef single_quote_func():\n    '''Single quoted docstring.'''\n    pass\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_docstring(func_node)
    expected = 'Single quoted docstring.'
    assert result == expected
