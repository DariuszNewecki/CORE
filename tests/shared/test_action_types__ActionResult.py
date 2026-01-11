"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/action_types.py
- Symbol: ActionResult
- Status: 13 tests passed, some failed
- Passing tests: test_basic_initialization, test_name_property_backwards_compatibility, test_validation_empty_action_id, test_validation_non_string_action_id, test_validation_non_dict_data, test_validation_non_bool_ok, test_data_size_limit_enforcement, test_data_with_non_serializable_content, test_default_field_factories, test_complex_nested_data, test_boolean_ok_values, test_action_id_with_dot_notation, test_unicode_in_data
- Generated: 2026-01-11 00:54:13
"""

import pytest
import json
from dataclasses import field
from typing import Any
from shared.action_types import ActionResult, ActionImpact

class TestActionResult:

    def test_basic_initialization(self):
        """Test basic initialization with required fields."""
        result = ActionResult(action_id='check.imports', ok=True, data={'violations_count': 0, 'files_scanned': 5})
        assert result.action_id == 'check.imports'
        assert result.ok == True
        assert result.data == {'violations_count': 0, 'files_scanned': 5}
        assert result.duration_sec == 0.0
        assert result.impact == None
        assert result.logs == []
        assert result.warnings == []
        assert result.suggestions == []

    def test_name_property_backwards_compatibility(self):
        """Test the name property alias for action_id."""
        result = ActionResult(action_id='generate.docs', ok=True, data={'files_created': ['README.md']})
        assert result.name == 'generate.docs'
        assert result.name == result.action_id

    def test_validation_empty_action_id(self):
        """Test validation rejects empty action_id."""
        with pytest.raises(ValueError, match='action_id must be non-empty string'):
            ActionResult(action_id='', ok=True, data={})

    def test_validation_non_string_action_id(self):
        """Test validation rejects non-string action_id."""
        with pytest.raises(ValueError, match='action_id must be non-empty string'):
            ActionResult(action_id=123, ok=True, data={})

    def test_validation_non_dict_data(self):
        """Test validation rejects non-dict data."""
        with pytest.raises(ValueError, match='data must be a dict'):
            ActionResult(action_id='check.test', ok=True, data='not a dict')

    def test_validation_non_bool_ok(self):
        """Test validation rejects non-boolean ok."""
        with pytest.raises(ValueError, match='ok must be a boolean'):
            ActionResult(action_id='check.test', ok='yes', data={})

    def test_data_size_limit_enforcement(self):
        """Test data size limit enforcement."""
        large_data = {'large_string': 'x' * (6 * 1024 * 1024)}
        with pytest.raises(ValueError, match='ActionResult.data exceeds size limit'):
            ActionResult(action_id='generate.large', ok=True, data=large_data)

    def test_data_with_non_serializable_content(self):
        """Test initialization with non-serializable data (should not crash)."""

        class CustomObject:

            def __repr__(self):
                return 'CustomObject()'
        result = ActionResult(action_id='test.nonserializable', ok=True, data={'obj': CustomObject(), 'number': 42})
        assert result.action_id == 'test.nonserializable'
        assert result.ok == True
        assert 'obj' in result.data
        assert result.data['number'] == 42

    def test_default_field_factories(self):
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

    def test_complex_nested_data(self):
        """Test initialization with complex nested data structures."""
        complex_data = {'violations': [{'file': '/path/to/file.py', 'line': 10, 'message': 'Invalid import'}, {'file': '/path/to/other.py', 'line': 20, 'message': 'Missing docstring'}], 'summary': {'total': 2, 'by_type': {'import': 1, 'docstring': 1}}, 'files_scanned': 15}
        result = ActionResult(action_id='check.complex', ok=False, data=complex_data, duration_sec=2.3)
        assert result.action_id == 'check.complex'
        assert result.ok == False
        assert result.data == complex_data
        assert result.duration_sec == 2.3
        assert len(result.data['violations']) == 2
        assert result.data['summary']['total'] == 2

    def test_boolean_ok_values(self):
        """Test both True and False values for ok field."""
        result_true = ActionResult(action_id='test.true', ok=True, data={'status': 'success'})
        assert result_true.ok == True
        result_false = ActionResult(action_id='test.false', ok=False, data={'status': 'failed'})
        assert result_false.ok == False

    def test_action_id_with_dot_notation(self):
        """Test action_id with various dot notation formats."""
        test_cases = ['fix.ids', 'check.imports', 'generate.docs', 'sync.files', 'validate.schema']
        for action_id in test_cases:
            result = ActionResult(action_id=action_id, ok=True, data={})
            assert result.action_id == action_id

    def test_unicode_in_data(self):
        """Test that ActionResult handles Unicode characters correctly."""
        unicode_data = {'message': 'Processing file…', 'details': 'Truncated with ellipsis…', 'items': ['item₁', 'item₂', 'item₃']}
        result = ActionResult(action_id='test.unicode', ok=True, data=unicode_data)
        assert result.data['message'] == 'Processing file…'
        assert result.data['details'] == 'Truncated with ellipsis…'
        assert result.data['items'] == ['item₁', 'item₂', 'item₃']
