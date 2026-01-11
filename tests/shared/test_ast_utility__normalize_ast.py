"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/ast_utility.py
- Symbol: normalize_ast
- Status: 4 tests passed, some failed
- Passing tests: test_normalize_ast_same_structure_different_names, test_normalize_ast_different_structure, test_normalize_ast_deepcopy_preservation, test_normalize_ast_empty_program
- Generated: 2026-01-11 01:12:54
"""

import ast

from shared.ast_utility import normalize_ast


def test_normalize_ast_same_structure_different_names():
    """Test that different variable names produce same normalized output."""
    code1 = "a = 1\nb = a + 2"
    code2 = "x = 1\ny = x + 2"
    tree1 = ast.parse(code1)
    tree2 = ast.parse(code2)
    result1 = normalize_ast(tree1)
    result2 = normalize_ast(tree2)
    assert result1 == result2


def test_normalize_ast_different_structure():
    """Test that structurally different code produces different output."""
    code1 = "x = 1 + 2"
    code2 = "x = 1 * 2"
    tree1 = ast.parse(code1)
    tree2 = ast.parse(code2)
    result1 = normalize_ast(tree1)
    result2 = normalize_ast(tree2)
    assert result1 != result2


def test_normalize_ast_deepcopy_preservation():
    """Test that original AST is not modified."""
    code = "original = 'should remain'"
    tree = ast.parse(code)
    original_dump = ast.dump(tree, indent=0)
    normalized = normalize_ast(tree)
    assert ast.dump(tree, indent=0) == original_dump
    assert normalized != original_dump
    assert "original" not in normalized
    assert "v0" in normalized


def test_normalize_ast_empty_program():
    """Test normalization of empty program."""
    code = ""
    tree = ast.parse(code)
    result = normalize_ast(tree)
    assert isinstance(result, str)
    assert "Module" in result
