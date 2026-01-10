"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/action_types.py
- Symbol: ActionResult
- Status: 11 tests passed, some failed
- Passing tests: test_action_result_initialization_with_required_fields, test_action_result_validation_empty_action_id, test_action_result_validation_non_string_action_id, test_action_result_validation_non_dict_data, test_action_result_validation_non_bool_ok, test_action_result_data_size_limit_enforced, test_action_result_with_non_serializable_data, test_action_result_name_property_backwards_compatibility, test_action_result_with_complex_nested_data, test_action_result_default_field_factories, test_action_result_with_file_paths_in_data
- Generated: 2026-01-11 00:10:03
"""

import pytest
import json
from dataclasses import field
from typing import Any
from shared.action_types import ActionResult, ActionImpact

def test_action_result_initialization_with_required_fields():
    """Test basic initialization with required fields."""
    result = ActionResult(action_id='check.imports', ok=True, data={'violations_count': 0, 'files_scanned': 5})
    assert result.action_id == 'check.imports'
    assert result.ok == True
    assert result.data == {'violations_count': 0, 'files_scanned': 5}
    assert result.duration_sec == 0.0
    assert result.impact is None
    assert result.logs == []
    assert result.warnings == []
    assert result.suggestions == []
    assert result.name == 'check.imports'

def test_action_result_validation_empty_action_id():
    """Test validation rejects empty action_id."""
    with pytest.raises(ValueError, match='action_id must be non-empty string'):
        ActionResult(action_id='', ok=True, data={})

def test_action_result_validation_non_string_action_id():
    """Test validation rejects non-string action_id."""
    with pytest.raises(ValueError, match='action_id must be non-empty string'):
        ActionResult(action_id=123, ok=True, data={})

def test_action_result_validation_non_dict_data():
    """Test validation rejects non-dict data."""
    with pytest.raises(ValueError, match='data must be a dict'):
        ActionResult(action_id='check.test', ok=True, data='not a dict')

def test_action_result_validation_non_bool_ok():
    """Test validation rejects non-boolean ok."""
    with pytest.raises(ValueError, match='ok must be a boolean'):
        ActionResult(action_id='check.test', ok='yes', data={})

def test_action_result_data_size_limit_enforced():
    """Test data size limit enforcement."""
    large_data = {'content': 'x' * (ActionResult.MAX_DATA_SIZE_BYTES + 100), 'metadata': {'timestamp': '2024-01-01'}}
    with pytest.raises(ValueError) as exc_info:
        ActionResult(action_id='generate.large', ok=True, data=large_data)
    assert 'exceeds size limit' in str(exc_info.value)
    assert str(ActionResult.MAX_DATA_SIZE_BYTES) in str(exc_info.value)
    assert 'generate.large' in str(exc_info.value)

def test_action_result_with_non_serializable_data():
    """Test ActionResult handles non-serializable data gracefully."""
    non_serializable_data = {'count': 5, 'func': lambda x: x * 2}
    result = ActionResult(action_id='check.special', ok=True, data=non_serializable_data)
    assert result.action_id == 'check.special'
    assert result.ok == True
    assert 'count' in result.data
    assert result.data['count'] == 5
    assert callable(result.data['func'])

def test_action_result_name_property_backwards_compatibility():
    """Test the name property for backwards compatibility."""
    result = ActionResult(action_id='sync.files', ok=True, data={'files_synced': 10})
    assert result.name == 'sync.files'
    assert result.name == result.action_id
    assert isinstance(ActionResult.name, property)

def test_action_result_with_complex_nested_data():
    """Test ActionResult with complex nested data structures."""
    complex_data = {'violations': [{'file': '/full/path/to/file.py', 'line': 42, 'rule': 'E501', 'message': 'Line too long'}, {'file': '/full/path/to/another.py', 'line': 15, 'rule': 'E302', 'message': 'Expected 2 blank lines'}], 'summary': {'total_violations': 2, 'files_with_violations': 2, 'by_rule': {'E501': 1, 'E302': 1}}}
    result = ActionResult(action_id='check.lint', ok=False, data=complex_data, suggestions=['Run fix.lint to auto-correct violations'])
    assert result.action_id == 'check.lint'
    assert result.ok == False
    assert len(result.data['violations']) == 2
    assert result.data['violations'][0]['file'] == '/full/path/to/file.py'
    assert result.data['summary']['total_violations'] == 2
    assert result.suggestions == ['Run fix.lint to auto-correct violations']

def test_action_result_default_field_factories():
    """Test that default_factory creates new lists for each instance."""
    result1 = ActionResult(action_id='test.1', ok=True, data={})
    result2 = ActionResult(action_id='test.2', ok=True, data={})
    result1.logs.append('log1')
    result1.warnings.append('warning1')
    result1.suggestions.append('suggestion1')
    assert result2.logs == []
    assert result2.warnings == []
    assert result2.suggestions == []
    assert result1.logs == ['log1']
    assert result1.warnings == ['warning1']
    assert result1.suggestions == ['suggestion1']

def test_action_result_with_file_paths_in_data():
    """Test ActionResult with file paths in data (full paths required)."""
    file_data = {'files_created': ['/full/path/to/project/src/main.py', '/full/path/to/project/src/utils.py'], 'files_modified': ['/full/path/to/project/README.md'], 'lines_added': 150, 'lines_removed': 45}
    result = ActionResult(action_id='generate.code', ok=True, data=file_data)
    assert result.action_id == 'generate.code'
    assert result.ok == True
    assert len(result.data['files_created']) == 2
    assert result.data['files_created'][0] == '/full/path/to/project/src/main.py'
    assert result.data['lines_added'] == 150
