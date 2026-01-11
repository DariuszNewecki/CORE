"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/ast_utility.py
- Symbol: calculate_structural_hash
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:12:13
"""

import pytest
from shared.ast_utility import calculate_structural_hash
import ast
import hashlib

# Detected return type: calculate_structural_hash returns a string (hex digest).

def test_calculate_structural_hash_basic_function():
    """Test hash calculation on a simple function node."""
    code = "def foo(x, y):\n    return x + y"
    node = ast.parse(code)
    hash_result = calculate_structural_hash(node)
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64  # SHA-256 hex digest length
    # Same structure, different whitespace/newlines should yield same hash.
    code2 = "def foo(x,y):return x+y"
    node2 = ast.parse(code2)
    hash_result2 = calculate_structural_hash(node2)
    assert hash_result == hash_result2

def test_calculate_structural_hash_insensitive_to_docstrings():
    """Test that docstrings are stripped and do not affect the hash."""
    code_with_doc = '''def bar():
    """This is a docstring."""
    pass'''
    code_without_doc = '''def bar():
    pass'''
    node1 = ast.parse(code_with_doc)
    node2 = ast.parse(code_without_doc)
    hash1 = calculate_structural_hash(node1)
    hash2 = calculate_structural_hash(node2)
    assert hash1 == hash2

def test_calculate_structural_hash_insensitive_to_whitespace():
    """Test that extra spaces and tabs are collapsed and do not affect hash."""
    code1 = "if  x   >   5:  pass"
    code2 = "if x>5:pass"
    node1 = ast.parse(code1)
    node2 = ast.parse(code2)
    hash1 = calculate_structural_hash(node1)
    hash2 = calculate_structural_hash(node2)
    assert hash1 == hash2

def test_calculate_structural_hash_class_with_methods():
    """Test hash on a more complex class structure."""
    code = """
class MyClass:
    def __init__(self, val):
        self.val = val
    def get_val(self):
        return self.val
"""
    node = ast.parse(code)
    hash_result = calculate_structural_hash(node)
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64

def test_calculate_structural_hash_fallback_on_exception():
    """Test that fallback hash is used when primary path fails."""
    # Create a node that will cause ast.unparse to fail in the primary path.
    # We can't easily break ast.unparse, but we can test the fallback
    # by mocking is not allowed. However, we can rely on the fact that the
    # function catches any Exception and uses a fallback.
    # We'll test that the function still returns a valid hash for a malformed node.
    class BadNode(ast.AST):
        pass
    node = BadNode()
    # This should trigger the exception path and use the fallback.
    hash_result = calculate_structural_hash(node)
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64

def test_calculate_structural_hash_module_node():
    """Test that the function works on a Module node (common case)."""
    code = "a = 1\nb = 2"
    node = ast.parse(code)  # This is a Module node
    hash_result = calculate_structural_hash(node)
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64

def test_calculate_structural_hash_empty_module():
    """Test hash on an empty module."""
    code = ""
    node = ast.parse(code)
    hash_result = calculate_structural_hash(node)
    assert isinstance(hash_result, str)
    assert len(hash_result) == 64

def test_calculate_structural_hash_different_structures_produce_different_hashes():
    """Test that structurally different code produces different hashes."""
    code1 = "def f(): pass"
    code2 = "def g(): pass"
    node1 = ast.parse(code1)
    node2 = ast.parse(code2)
    hash1 = calculate_structural_hash(node1)
    hash2 = calculate_structural_hash(node2)
    assert hash1 != hash2
