"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/ast_utility.py
- Symbol: SymbolIdResult
- Status: 6 tests passed, some failed
- Passing tests: test_symbol_id_result_initialization_with_values, test_symbol_id_result_initialization_partial, test_symbol_id_result_equality, test_symbol_id_result_inequality, test_symbol_id_result_attribute_types, test_symbol_id_result_none_uuid_and_line
- Generated: 2026-01-11 01:08:28
"""

import pytest
from shared.ast_utility import SymbolIdResult

def test_symbol_id_result_initialization_with_values():
    """Test initialization with all values provided."""
    result = SymbolIdResult(has_id=True, uuid='123e4567-e89b-12d3-a456-426614174000', id_tag_line_num=42, definition_line_num=100)
    assert result.has_id == True
    assert result.uuid == '123e4567-e89b-12d3-a456-426614174000'
    assert result.id_tag_line_num == 42
    assert result.definition_line_num == 100

def test_symbol_id_result_initialization_partial():
    """Test initialization with only some values provided."""
    result = SymbolIdResult(has_id=False, definition_line_num=5)
    assert result.has_id == False
    assert result.uuid == None
    assert result.id_tag_line_num == None
    assert result.definition_line_num == 5

def test_symbol_id_result_equality():
    """Test that two instances with same data are equal (by value)."""
    result1 = SymbolIdResult(has_id=True, uuid='abc', id_tag_line_num=1, definition_line_num=2)
    result2 = SymbolIdResult(has_id=True, uuid='abc', id_tag_line_num=1, definition_line_num=2)
    assert result1 == result2
    assert result1.has_id == result2.has_id
    assert result1.uuid == result2.uuid
    assert result1.id_tag_line_num == result2.id_tag_line_num
    assert result1.definition_line_num == result2.definition_line_num

def test_symbol_id_result_inequality():
    """Test that instances with different data are not equal."""
    result1 = SymbolIdResult(has_id=True, uuid='abc', id_tag_line_num=1, definition_line_num=2)
    result2 = SymbolIdResult(has_id=False, uuid='def', id_tag_line_num=3, definition_line_num=4)
    assert result1 != result2

def test_symbol_id_result_attribute_types():
    """Verify the types of the attributes."""
    result = SymbolIdResult(has_id=True, uuid='test-uuid', id_tag_line_num=10, definition_line_num=20)
    assert isinstance(result.has_id, bool)
    assert isinstance(result.uuid, str)
    assert isinstance(result.id_tag_line_num, int)
    assert isinstance(result.definition_line_num, int)

def test_symbol_id_result_none_uuid_and_line():
    """Test that uuid and id_tag_line_num can be None when has_id is False."""
    result = SymbolIdResult(has_id=False, uuid=None, id_tag_line_num=None, definition_line_num=1)
    assert result.has_id == False
    assert result.uuid == None
    assert result.id_tag_line_num == None
    assert result.definition_line_num == 1
