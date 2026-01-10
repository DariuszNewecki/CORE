"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/component_primitive.py
- Symbol: ComponentResult
- Status: 13 tests passed, some failed
- Passing tests: test_component_result_initialization_with_minimal_required_fields, test_component_result_validation_empty_component_id, test_component_result_validation_non_string_component_id, test_component_result_validation_non_dict_data, test_component_result_validation_confidence_below_zero, test_component_result_validation_confidence_above_one, test_component_result_edge_case_confidence_zero, test_component_result_edge_case_confidence_one, test_component_result_metadata_default_factory_creates_new_dict, test_component_result_next_suggested_can_be_empty_string, test_component_result_duration_can_be_zero, test_component_result_duration_can_be_positive, test_component_result_boolean_ok_field
- Generated: 2026-01-11 00:15:16
"""

import pytest
from shared.component_primitive import ComponentResult
from shared.component_primitive import ComponentPhase

def test_component_result_initialization_with_minimal_required_fields():
    """Test basic initialization with only required fields."""
    result = ComponentResult(component_id='test_component', ok=True, data={'key': 'value'}, phase=ComponentPhase.EXECUTION)
    assert result.component_id == 'test_component'
    assert result.ok == True
    assert result.data == {'key': 'value'}
    assert result.phase == ComponentPhase.EXECUTION
    assert result.confidence == 1.0
    assert result.next_suggested == ''
    assert result.metadata == {}
    assert result.duration_sec == 0.0

def test_component_result_validation_empty_component_id():
    """Test validation rejects empty component_id."""
    with pytest.raises(ValueError, match='ComponentResult.component_id must be non-empty string'):
        ComponentResult(component_id='', ok=True, data={}, phase=ComponentPhase.EXECUTION)

def test_component_result_validation_non_string_component_id():
    """Test validation rejects non-string component_id."""
    with pytest.raises(ValueError, match='ComponentResult.component_id must be non-empty string'):
        ComponentResult(component_id=123, ok=True, data={}, phase=ComponentPhase.EXECUTION)

def test_component_result_validation_non_dict_data():
    """Test validation rejects non-dict data."""
    with pytest.raises(ValueError, match='ComponentResult.data must be dict'):
        ComponentResult(component_id='test', ok=True, data='not a dict', phase=ComponentPhase.EXECUTION)

def test_component_result_validation_confidence_below_zero():
    """Test validation rejects confidence below 0.0."""
    with pytest.raises(ValueError, match='ComponentResult.confidence must be in \\[0.0, 1.0\\]'):
        ComponentResult(component_id='test', ok=True, data={}, phase=ComponentPhase.EXECUTION, confidence=-0.1)

def test_component_result_validation_confidence_above_one():
    """Test validation rejects confidence above 1.0."""
    with pytest.raises(ValueError, match='ComponentResult.confidence must be in \\[0.0, 1.0\\]'):
        ComponentResult(component_id='test', ok=True, data={}, phase=ComponentPhase.EXECUTION, confidence=1.1)

def test_component_result_edge_case_confidence_zero():
    """Test confidence can be exactly 0.0."""
    result = ComponentResult(component_id='test', ok=True, data={}, phase=ComponentPhase.EXECUTION, confidence=0.0)
    assert result.confidence == 0.0

def test_component_result_edge_case_confidence_one():
    """Test confidence can be exactly 1.0."""
    result = ComponentResult(component_id='test', ok=True, data={}, phase=ComponentPhase.EXECUTION, confidence=1.0)
    assert result.confidence == 1.0

def test_component_result_metadata_default_factory_creates_new_dict():
    """Test that default_factory creates new dict instances for each object."""
    result1 = ComponentResult(component_id='test1', ok=True, data={}, phase=ComponentPhase.EXECUTION)
    result2 = ComponentResult(component_id='test2', ok=True, data={}, phase=ComponentPhase.EXECUTION)
    assert result1.metadata == {}
    assert result2.metadata == {}
    result1.metadata['key'] = 'value1'
    result2.metadata['key'] = 'value2'
    assert result1.metadata == {'key': 'value1'}
    assert result2.metadata == {'key': 'value2'}

def test_component_result_next_suggested_can_be_empty_string():
    """Test next_suggested field can be empty string."""
    result = ComponentResult(component_id='test', ok=True, data={}, phase=ComponentPhase.EXECUTION, next_suggested='')
    assert result.next_suggested == ''

def test_component_result_duration_can_be_zero():
    """Test duration_sec can be 0.0."""
    result = ComponentResult(component_id='instant_component', ok=True, data={}, phase=ComponentPhase.EXECUTION, duration_sec=0.0)
    assert result.duration_sec == 0.0

def test_component_result_duration_can_be_positive():
    """Test duration_sec can be positive float."""
    result = ComponentResult(component_id='slow_component', ok=True, data={}, phase=ComponentPhase.EXECUTION, duration_sec=123.456)
    assert result.duration_sec == 123.456

def test_component_result_boolean_ok_field():
    """Test ok field accepts both True and False."""
    result_true = ComponentResult(component_id='success', ok=True, data={}, phase=ComponentPhase.EXECUTION)
    result_false = ComponentResult(component_id='failure', ok=False, data={}, phase=ComponentPhase.EXECUTION)
    assert result_true.ok == True
    assert result_false.ok == False
