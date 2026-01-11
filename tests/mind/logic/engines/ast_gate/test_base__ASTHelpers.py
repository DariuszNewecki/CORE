"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/base.py
- Symbol: ASTHelpers
- Status: 19 tests passed, some failed
- Passing tests: test_lineno_returns_zero_for_node_without_lineno, test_lineno_returns_lineno_when_present, test_lineno_returns_zero_when_lineno_is_falsy, test_full_attr_name_returns_none_for_unsupported_node, test_full_attr_name_returns_name_id, test_full_attr_name_returns_single_attribute, test_full_attr_name_returns_nested_attribute_chain, test_full_attr_name_handles_attribute_with_none_left, test_matches_call_exact_match, test_matches_call_no_match, test_matches_call_suffix_match_with_dot, test_matches_call_prevents_bare_leaf_false_positive, test_matches_call_matches_full_pattern_at_end, test_matches_call_handles_multiple_patterns, test_matches_call_handles_pattern_without_dot, test_matches_call_complex_suffix_matching, test_matches_call_rejects_partial_suffix, test_iter_module_level_stmts_returns_body_for_module, test_iter_module_level_stmts_returns_empty_for_non_module
- Generated: 2026-01-11 02:25:02
"""

import pytest
from mind.logic.engines.ast_gate.base import ASTHelpers
import ast
from typing import Iterable

def test_lineno_returns_zero_for_node_without_lineno():
    """Test lineno returns 0 when node lacks lineno attribute."""
    node = ast.AST()
    result = ASTHelpers.lineno(node)
    assert result == 0

def test_lineno_returns_lineno_when_present():
    """Test lineno extracts line number from node."""
    node = ast.AST()
    node.lineno = 42
    result = ASTHelpers.lineno(node)
    assert result == 42

def test_lineno_returns_zero_when_lineno_is_falsy():
    """Test lineno returns 0 when lineno is 0 or None."""
    node = ast.AST()
    node.lineno = 0
    result = ASTHelpers.lineno(node)
    assert result == 0

def test_full_attr_name_returns_none_for_unsupported_node():
    """Test full_attr_name returns None for non-Name/Attribute nodes."""
    node = ast.Constant(value=42)
    result = ASTHelpers.full_attr_name(node)
    assert result is None

def test_full_attr_name_returns_name_id():
    """Test full_attr_name returns id for ast.Name."""
    node = ast.Name(id='asyncio', ctx=ast.Load())
    result = ASTHelpers.full_attr_name(node)
    assert result == 'asyncio'

def test_full_attr_name_returns_single_attribute():
    """Test full_attr_name returns attr for single Attribute."""
    value = ast.Name(id='asyncio', ctx=ast.Load())
    node = ast.Attribute(value=value, attr='run', ctx=ast.Load())
    result = ASTHelpers.full_attr_name(node)
    assert result == 'asyncio.run'

def test_full_attr_name_returns_nested_attribute_chain():
    """Test full_attr_name resolves deeply nested attributes."""
    foo = ast.Name(id='foo', ctx=ast.Load())
    bar = ast.Attribute(value=foo, attr='bar', ctx=ast.Load())
    baz = ast.Attribute(value=bar, attr='baz', ctx=ast.Load())
    qux = ast.Attribute(value=baz, attr='qux', ctx=ast.Load())
    result = ASTHelpers.full_attr_name(qux)
    assert result == 'foo.bar.baz.qux'

def test_full_attr_name_handles_attribute_with_none_left():
    """Test full_attr_name returns attr when left side resolves to None."""
    value = ast.Constant(value=42)
    node = ast.Attribute(value=value, attr='run', ctx=ast.Load())
    result = ASTHelpers.full_attr_name(node)
    assert result == 'run'

def test_matches_call_exact_match():
    """Test matches_call returns True for exact match."""
    result = ASTHelpers.matches_call('asyncio.run', ['asyncio.run'])
    assert result == True

def test_matches_call_no_match():
    """Test matches_call returns False when no patterns match."""
    result = ASTHelpers.matches_call('asyncio.run', ['subprocess.run'])
    assert result == False

def test_matches_call_suffix_match_with_dot():
    """Test matches_call matches suffix with proper dot boundary."""
    result = ASTHelpers.matches_call('foo.bar.asyncio.run', ['asyncio.run'])
    assert result == True

def test_matches_call_prevents_bare_leaf_false_positive():
    """Test matches_call prevents 'subprocess.run' matching 'run' pattern."""
    result = ASTHelpers.matches_call('subprocess.run', ['run'])
    assert result == False

def test_matches_call_matches_full_pattern_at_end():
    """Test matches_call matches when pattern appears at end with dot."""
    result = ASTHelpers.matches_call('myapp.asyncio.run', ['asyncio.run'])
    assert result == True

def test_matches_call_handles_multiple_patterns():
    """Test matches_call checks all patterns."""
    result = ASTHelpers.matches_call('asyncio.run', ['subprocess.run', 'asyncio.run', 'threading.Thread'])
    assert result == True

def test_matches_call_handles_pattern_without_dot():
    """Test matches_call with pattern that has no dot."""
    result = ASTHelpers.matches_call('run', ['run'])
    assert result == True

def test_matches_call_complex_suffix_matching():
    """Test matches_call suffix matching with multiple parts."""
    result = ASTHelpers.matches_call('a.b.c.d.e.f', ['d.e.f'])
    assert result == True

def test_matches_call_rejects_partial_suffix():
    """Test matches_call rejects when suffix parts don't fully match."""
    result = ASTHelpers.matches_call('a.b.c.d.e.f', ['e.f.g'])
    assert result == False

def test_iter_module_level_stmts_returns_body_for_module():
    """Test iter_module_level_stmts returns body for ast.Module."""
    tree = ast.Module(body=[ast.Expr(value=ast.Constant(value=1))], type_ignores=[])
    result = ASTHelpers.iter_module_level_stmts(tree)
    assert list(result) == tree.body

def test_iter_module_level_stmts_returns_empty_for_non_module():
    """Test iter_module_level_stmts returns empty for non-Module nodes."""
    tree = ast.ClassDef(name='Test', body=[], bases=[], keywords=[])
    result = ASTHelpers.iter_module_level_stmts(tree)
    assert list(result) == []
