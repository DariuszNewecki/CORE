"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/ast_utility.py
- Symbol: find_definition_line
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:08:05
"""

import pytest
from shared.ast_utility import find_definition_line
import ast

# Detected return type: int (1-based line number)

def test_find_definition_line_no_decorators():
    """Test function/class without decorators returns node.lineno."""
    source = """def my_function():
    pass

class MyClass:
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)

    # Test function without decorators
    func_node = module.body[0]
    assert find_definition_line(func_node, source_lines) == 1

    # Test class without decorators
    class_node = module.body[1]
    assert find_definition_line(class_node, source_lines) == 4

def test_find_definition_line_with_decorators():
    """Test function with decorators finds correct definition line."""
    source = """@decorator1
@decorator2
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 3

def test_find_definition_line_async_function():
    """Test async function with decorators."""
    source = """@decorator
async def async_func():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 2

def test_find_definition_line_class_with_decorators():
    """Test class with decorators."""
    source = """@dataclass
class MyClass:
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    class_node = module.body[0]

    assert find_definition_line(class_node, source_lines) == 2

def test_find_definition_line_multiple_decorators():
    """Test function with multiple decorators."""
    source = """@decorator1
@decorator2
@decorator3
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 4

def test_find_definition_line_decorators_with_arguments():
    """Test decorators with arguments."""
    source = """@decorator(arg1, arg2)
@another_decorator
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 3

def test_find_definition_line_blank_lines_between_decorators():
    """Test with blank lines between decorators."""
    source = """@decorator1

@decorator2

def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 5

def test_find_definition_line_indented_decorators():
    """Test decorators with indentation (e.g., inside class)."""
    source = """class Outer:
    @decorator1
    @decorator2
    def method(self):
        pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    class_node = module.body[0]
    func_node = class_node.body[0]

    assert find_definition_line(func_node, source_lines) == 4

def test_find_definition_line_complex_decorator_expressions():
    """Test complex decorator expressions."""
    source = """@decorator1(arg1, arg2)
@decorator2().method()
@decorator3[item]
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 4

def test_find_definition_line_fallback_when_not_found():
    """Test fallback to node.lineno when definition not found after decorators."""
    source = """@decorator
# Some comment
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    # The function should fall back to node.lineno when it can't find "def my_function"
    # after the decorator. In this case, node.lineno should be 3 (1-based).
    assert find_definition_line(func_node, source_lines) == 3

def test_find_definition_line_same_name_in_comment():
    """Test when function name appears in comment after decorator."""
    source = """@decorator
# Not the real my_function
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    assert find_definition_line(func_node, source_lines) == 3

def test_find_definition_line_empty_source_lines():
    """Test with empty source lines list."""
    source_lines = []
    module = ast.parse("def my_function(): pass")
    func_node = module.body[0]

    # Should fall back to node.lineno (which is 1)
    assert find_definition_line(func_node, source_lines) == 1

def test_find_definition_line_end_lineno_used():
    """Test that end_lineno is used when available for last decorator."""
    source = """@decorator(arg1,
              arg2,
              arg3)
def my_function():
    pass"""

    source_lines = source.splitlines()
    module = ast.parse(source)
    func_node = module.body[0]

    # The decorator spans lines 1-3, so search should start from line 3
    assert find_definition_line(func_node, source_lines) == 4
